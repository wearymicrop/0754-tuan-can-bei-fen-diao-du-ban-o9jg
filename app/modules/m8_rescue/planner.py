"""故障车救援的纯计算环节。

只搬运故障车上已装车的实物餐：每份救援移动都能回溯到原车的一条装车记录，
不新占库存、不重复耗餐。接运车可以是同批次尚有余位的车次，也可以是后到的备用车。
"""
from collections import defaultdict

from app.errors import DomainError
from app.records import entry, token
from app.modules.m4_capacity.trips import parse as parse_trip

NO_RESCUE_TRUCK = 'NO_RESCUE_TRUCK'
RESCUE_FULL = 'RESCUE_FULL'
RESCUE_LOT_UNSAFE = 'RESCUE_LOT_UNSAFE'

DETAIL = {
    NO_RESCUE_TRUCK: '没有能在交接窗内抵达该站点的接运车',
    RESCUE_FULL: '满足窗口的接运车余位不足',
    RESCUE_LOT_UNSAFE: '接运车到站时批号已失效或尚未就绪',
}


def parse_backup(raw, cutoff, existing):
    if not isinstance(raw, dict):
        raise DomainError('BACKUP_SCHEMA', '备用车须为车次记录对象')
    try:
        trip = parse_trip(entry('rescue', 1, raw))
    except ValueError as error:
        raise DomainError('BACKUP_SCHEMA', f'备用车车次无效：{error}') from error
    if trip['truck'] in existing:
        raise DomainError('BACKUP_DUPLICATE_ID', '备用车编号与既有车次冲突')
    if trip['departure'] < cutoff:
        raise DomainError('BACKUP_DEPARTED', '备用车出发时间早于批次截点')
    return trip


def _station_windows(result):
    table = defaultdict(list)
    for row in result['windows']['rows']:
        table[row['station']].append(row)
    return table


def _order_windows(result):
    return {row['order']: row['window'] for row in result['windows']['demands'] if row.get('window')}


def build_carriers(result, failed_trip, cutoff, backup_raw, engaged_failed, prior_backup_specs, prior_moves):
    """生成同波次候选接运车，余位先扣除本运行已发布救援占用的份数。"""
    failed_truck = failed_trip['truck']
    carriers = {}
    for row in result['allocation']['vehicles']:
        if row['truck'] == failed_truck or row['truck'] in engaged_failed:
            continue
        if row['wave'] != failed_trip['wave']:
            continue
        carriers[row['truck']] = {
            'truck': row['truck'], 'wave': row['wave'], 'capacity': row['capacity'],
            'departure': row['departure'], 'stops': row['stops'],
            'original_loaded': row['loaded'], 'remaining': row['remaining'],
            'rescued_in': 0, 'role': 'rescue', 'source': 'trip',
        }
    for spec in prior_backup_specs:
        if spec['wave'] != failed_trip['wave']:
            continue
        trip = parse_backup(spec, cutoff, set())
        carriers[trip['truck']] = {
            'truck': trip['truck'], 'wave': trip['wave'], 'capacity': trip['capacity'],
            'departure': trip['departure'], 'stops': trip['stops'],
            'original_loaded': 0, 'remaining': trip['capacity'],
            'rescued_in': 0, 'role': 'backup', 'source': 'backup',
        }
    backup = None
    if backup_raw is not None:
        backup = parse_backup(backup_raw, cutoff, {truck: None for truck in carriers})
        if backup['wave'] != failed_trip['wave']:
            raise DomainError('BACKUP_WRONG_WAVE', '备用车波次必须与故障车一致')
        if backup['truck'] in carriers:
            raise DomainError('BACKUP_DUPLICATE_ID', '备用车编号与既有车次冲突')
        carriers[backup['truck']] = {
            'truck': backup['truck'], 'wave': backup['wave'], 'capacity': backup['capacity'],
            'departure': backup['departure'], 'stops': backup['stops'],
            'original_loaded': 0, 'remaining': backup['capacity'],
            'rescued_in': 0, 'role': 'backup', 'source': 'backup',
        }
    for move in prior_moves:
        carrier = carriers.get(move['to_truck'])
        if carrier is None:
            continue
        carrier['remaining'] -= move['qty']
        carrier['rescued_in'] += move['qty']
    return carriers, backup


def _on_time_stop(carrier, station, window):
    for stop in carrier['stops']:
        if stop['station'] == station and window['start'] <= stop['eta'] < window['end']:
            return stop
    return None


def plan(result, failed_truck, cutoff, backup_raw=None, engaged_failed=frozenset(),
         prior_backup_specs=(), prior_moves=()):
    """返回救援预案（未送达、移动明细、车辆份数与逐项核对标志）。"""
    allocation = result['allocation']
    trips = {row['truck']: row for row in allocation['vehicles']}
    if not token(failed_truck):
        raise DomainError('RESCUE_TRUCK_REQUIRED', '请指定故障车辆')
    if failed_truck not in trips:
        raise DomainError('RESCUE_TRUCK_UNKNOWN', '故障车辆不在本批次车次中', 404)
    source_loads = [load for order in allocation['rows'] for load in order['loads']
                    if load['truck'] == failed_truck]
    if not source_loads:
        raise DomainError('RESCUE_NOTHING', '该故障车没有已装车餐，无需救援')
    stock_by_lot = {row['lot']: row for row in allocation['stock']}
    windows_by_order = _order_windows(result)
    station_windows = _station_windows(result)
    failed_trip = trips[failed_truck]
    carriers, backup = build_carriers(
        result, failed_trip, cutoff, backup_raw, engaged_failed, prior_backup_specs, prior_moves)

    affected = defaultdict(list)
    for order in allocation['rows']:
        for load in order['loads']:
            if load['truck'] == failed_truck:
                affected[order['order']].append((order, load))
    ordered_orders = sorted(affected, key=lambda ident: (
        not affected[ident][0][0]['locked'],
        windows_by_order[ident]['end'], ident))

    moves, order_rows, issues = [], [], []
    moved_by_lot = defaultdict(int)
    for ident in ordered_orders:
        pairs = affected[ident]
        order = pairs[0][0]
        window = windows_by_order[ident]
        order_moves, order_remaining = [], sum(load['qty'] for _, load in pairs)
        affected_qty = order_remaining
        seen_stop = seen_fresh = seen_room = False
        source = sorted((load for _, load in pairs),
                        key=lambda load: (stock_by_lot[load['lot']]['expires'], load['lot']))
        for load in source:
            lot_row = stock_by_lot[load['lot']]
            lot_left = load['qty']
            options = []
            for carrier in carriers.values():
                stop = _on_time_stop(carrier, load['station'], window)
                if stop is None:
                    continue
                fresh = lot_row['ready'] <= carrier['departure'] and lot_row['expires'] > stop['eta']
                options.append((stop, carrier, fresh))
            options.sort(key=lambda item: (item[0]['eta'], item[1]['truck']))
            lot_seen_fresh = lot_seen_room = False
            for stop, carrier, fresh in options:
                if not lot_left:
                    break
                seen_stop = True
                if not fresh:
                    continue
                seen_fresh = lot_seen_fresh = True
                if carrier['remaining'] <= 0:
                    continue
                seen_room = lot_seen_room = True
                qty = min(lot_left, carrier['remaining'])
                lot_left -= qty
                carrier['remaining'] -= qty
                carrier['rescued_in'] += qty
                moved_by_lot[load['lot']] += qty
                move = {
                    'order': ident, 'station': load['station'], 'lot': load['lot'],
                    'meal': load['meal'], 'kind': load['kind'], 'qty': qty,
                    'from_truck': failed_truck, 'to_truck': carrier['truck'],
                    'arrival': stop['arrival'], 'eta': stop['eta'],
                    'order_line': load['order_line'], 'stock_line': load['stock_line'],
                    'trip_line': load['trip_line'], 'window_line': load['window_line'],
                    'substitution_line': load['substitution_line'],
                }
                moves.append(move)
                order_moves.append(move)
            order_remaining -= load['qty'] - lot_left
        rescued = affected_qty - order_remaining
        code = None
        if order_remaining:
            # 未送达原因按事实取最贴切的一条：无准点车 → 余位耗尽 → 批号到不了接运站。
            if not seen_stop:
                code = NO_RESCUE_TRUCK
            elif seen_fresh and not seen_room:
                code = RESCUE_FULL
            else:
                code = RESCUE_LOT_UNSAFE
            issues.append({**entry('rescue', order['line'], order.get('raw', {})),
                           'code': code, 'detail': DETAIL[code], 'order': ident})
        order_rows.append({
            'order': ident, 'station': order['station'], 'wave': order['wave'],
            'meal': order['meal'], 'locked': bool(order['locked']),
            'affected_qty': affected_qty, 'rescued_qty': rescued,
            'undelivered_qty': order_remaining, 'window_end': window['end'],
            'window_line': window['line'], 'code': code, 'moves': order_moves,
        })

    vehicles = _vehicle_summary(result, failed_truck, carriers, source_loads, moves)
    checks = _checks(result, failed_truck, source_loads, moves, order_rows, moved_by_lot,
                     carriers, vehicles, station_windows, stock_by_lot)
    return {
        'failed_truck': failed_truck,
        'backup': backup and {
            'truck': backup['truck'], 'wave': backup['wave'], 'capacity': backup['capacity'],
            'departure': backup['departure'],
            'stops': [{'station': stop['station'], 'arrival': stop['arrival']} for stop in backup['stops']],
        },
        'orders': order_rows, 'moves': moves, 'vehicles': vehicles,
        'checks': checks, 'issues': issues,
        'status': 'MATCHED' if all(checks[name] for name in (
            'orders_balanced', 'lots_conserved', 'capacity_ok',
            'windows_ok', 'freshness_ok', 'fleet_total_conserved'))
        else 'CHECK_REQUIRED',
    }


def _vehicle_summary(result, failed_truck, carriers, source_loads, moves):
    original_by_truck = {row['truck']: row for row in result['allocation']['vehicles']}
    moved_out = sum(move['qty'] for move in moves)
    rows = []
    failed = original_by_truck[failed_truck]
    rows.append({'truck': failed_truck, 'role': 'failed', 'wave': failed['wave'],
                 'capacity': failed['capacity'], 'original_loaded': failed['loaded'],
                 'rescued_loaded': moved_out, 'final_loaded': 0,
                 'remaining_capacity': failed['capacity'],
                 'undelivered': failed['loaded'] - moved_out})
    for truck, carrier in sorted(carriers.items()):
        original = carrier['original_loaded']
        final = original + carrier['rescued_in']
        rows.append({'truck': truck, 'role': carrier['role'], 'wave': carrier['wave'],
                     'capacity': carrier['capacity'], 'original_loaded': original,
                     'rescued_loaded': carrier['rescued_in'], 'final_loaded': final,
                     'remaining_capacity': carrier['capacity'] - final,
                     'undelivered': 0})
    for row in result['allocation']['vehicles']:
        if row['truck'] == failed_truck or row['truck'] in carriers:
            continue
        rows.append({'truck': row['truck'], 'role': 'idle', 'wave': row['wave'],
                     'capacity': row['capacity'], 'original_loaded': row['loaded'],
                     'rescued_loaded': 0, 'final_loaded': row['loaded'],
                     'remaining_capacity': row['remaining'], 'undelivered': 0})
    return rows


def _checks(result, failed_truck, source_loads, moves, order_rows, moved_by_lot,
            carriers, vehicles, station_windows, stock_by_lot):
    source_by_lot = defaultdict(int)
    for load in source_loads:
        source_by_lot[load['lot']] += load['qty']
    lots_conserved = all(moved_by_lot[lot] <= qty for lot, qty in source_by_lot.items())
    lots_conserved &= set(moved_by_lot) <= set(source_by_lot)
    orders_balanced = all(
        row['affected_qty'] == row['rescued_qty'] + row['undelivered_qty']
        and row['rescued_qty'] == sum(move['qty'] for move in row['moves'])
        for row in order_rows)
    capacity_ok = all(0 <= row['remaining_capacity'] and row['final_loaded'] <= row['capacity']
                      for row in vehicles if row['role'] != 'failed')
    windows_ok = True
    freshness_ok = True
    for move in moves:
        windows = station_windows[move['station']]
        if not any(window['start'] <= move['eta'] < window['end'] for window in windows):
            windows_ok = False
        lot = stock_by_lot[move['lot']]
        carrier = next(item for item in carriers.values() if item['truck'] == move['to_truck'])
        stop = next(stop for stop in carrier['stops'] if stop['station'] == move['station'])
        if not (lot['ready'] <= carrier['departure'] and lot['expires'] > stop['eta']):
            freshness_ok = False
    original_total = sum(row['loaded'] for row in result['allocation']['vehicles'])
    final_total = sum(row['final_loaded'] for row in vehicles)
    undelivered_total = sum(row['undelivered'] for row in vehicles)
    fleet_total_conserved = original_total == final_total + undelivered_total
    source_total = sum(source_by_lot.values())
    moved_total = sum(move['qty'] for move in moves)
    return {
        'orders_balanced': orders_balanced,
        'lots_conserved': lots_conserved and moved_total <= source_total,
        'capacity_ok': capacity_ok,
        'windows_ok': windows_ok,
        'freshness_ok': freshness_ok,
        'fleet_total_conserved': fleet_total_conserved,
        'fully_covered': moved_total == source_total,
    }
