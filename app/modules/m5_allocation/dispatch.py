from collections import defaultdict


def assign(demands, trips, stock, approved):
    candidates = defaultdict(list)
    for trip in trips:
        for stop in trip['stops']:
            if stop['on_time']:
                candidates[trip['wave'],stop['station']].append((stop,trip))
    capacity = {row['truck']:row['capacity'] for row in trips}
    lots_by_meal = defaultdict(list)
    for lot in stock:
        if lot['status']=='usable':
            lots_by_meal[lot['meal']].append(lot)
    edges = defaultdict(dict)
    for row in approved:
        edges[row['requested']][row['spare']] = row['line']
    valid = sorted((row for row in demands if not row['dispute']),
                   key=lambda row: (not row['locked'],row['window']['end'],row['order']))
    output = []
    for rank, order in enumerate(valid,1):
        remaining, loads = order['qty'], []
        eligible = candidates.get((order['wave'],order['station']),[])
        substitutes = {} if order['locked'] else edges[order['meal']]
        lots = [(lot,None) for lot in lots_by_meal[order['meal']]]
        lots.extend((lot,line) for meal,line in sorted(substitutes.items()) for lot in lots_by_meal[meal] if lot['kind']=='spare')
        sorted_lots = sorted(lots, key=lambda option: (
            2 if option[1] is not None else int(option[0]['kind']=='spare'),
            option[0]['expires'], option[0]['lot']))
        sorted_trips = sorted(eligible,key=lambda option: (option[0]['eta'],option[1]['truck']))
        for lot,line in sorted_lots:
            if not remaining or not any(capacity[trip['truck']] for _,trip in sorted_trips):
                break
            if not lot['left']:
                continue
            for stop,trip in sorted_trips:
                truck = trip['truck']
                if lot['ready'] > trip['departure'] or lot['expires'] <= stop['eta']:
                    continue
                qty = min(remaining,capacity[truck],lot['left'])
                if not qty:
                    continue
                remaining -= qty
                capacity[truck] -= qty
                lot['left'] -= qty
                lot['loaded'] += qty
                loads.append({'order':order['order'],'order_line':order['line'],'truck':truck,'trip_line':trip['line'],
                              'lot':lot['lot'],'stock_line':lot['line'],'meal':lot['meal'],'kind':lot['kind'],'qty':qty,
                              'station':stop['station'],'arrival':stop['arrival'],'substitution_line':line,
                              'window_line':order['window']['line']})
                if not remaining or not lot['left']:
                    break
        code = None
        if remaining:
            if not eligible:
                code = 'NO_ON_TIME_TRUCK'
            elif not any(capacity[truck['truck']] for _,truck in eligible):
                code = 'TRUCK_FULL'
            else:
                code = 'NO_VALID_STOCK'
        output.append({**order,'rank':rank,'loads':loads,'shipped':order['qty']-remaining,'short':remaining,'disputed':0,'code':code})
    output.extend({**order,'rank':None,'loads':[],'shipped':0,'short':0,'disputed':order['qty'],'code':order['dispute']}
                  for order in demands if order['dispute'])
    return output, capacity
