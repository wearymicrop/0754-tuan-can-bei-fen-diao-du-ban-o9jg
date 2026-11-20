"""M8 故障救援：裁决、对账、幂等与 API。"""
from app.clock import instant
from app.modules.m8_rescue.planner import plan
from app.pipeline import evaluate
from app.source import load_sample


def backup_truck(capacity=60, departure="2026-11-20T11:50:00+08:00", stops=None):
    return {
        "truck": "备-甲", "wave": "午线", "capacity": capacity, "departure": departure,
        "stops": stops or [
            {"station": "创客园", "eta": "2026-11-20T11:58:00+08:00"},
            {"station": "运动馆", "eta": "2026-11-20T12:05:00+08:00"},
        ],
    }


def rescue(result, failed="柿-03", backup=None):
    cutoff = instant(result["at"] if "at" in result else "2026-11-20T09:30:00+08:00")
    return plan(result, failed, cutoff, backup)


def pick(records, order):
    return next(row for row in records["orders"] if row["order"] == order)


def test_locked_orders_rescued_before_flexible_with_limited_capacity(dirty_result):
    # 备用车只能再装 9 份：锁定的 团-011（9 份）应优先于弹性的 团-008/团-009 占位。
    draft = rescue(dirty_result, backup=backup_truck(capacity=9))
    locked = pick(draft, "团-011")
    flexible = pick(draft, "团-008")
    assert locked["rescued_qty"] == 9 and locked["undelivered_qty"] == 0
    assert flexible["rescued_qty"] == 0
    assert {move["to_truck"] for move in locked["moves"]} == {"备-甲"}


def test_moves_only_transfer_existing_lots_without_double_consumption(dirty_result):
    draft = rescue(dirty_result, backup=backup_truck(capacity=90))
    source_lots = {}
    for order in dirty_result["allocation"]["rows"]:
        for load in order["loads"]:
            if load["truck"] == "柿-03":
                source_lots[load["lot"]] = source_lots.get(load["lot"], 0) + load["qty"]
    moved = {}
    for move in draft["moves"]:
        moved[move["lot"]] = moved.get(move["lot"], 0) + move["qty"]
    # 每条救援移动都来自原车批号，且份数不超过原车实载。
    assert set(moved) <= set(source_lots)
    assert all(moved.get(lot, 0) <= qty for lot, qty in source_lots.items())
    assert draft["checks"]["lots_conserved"]


def test_lot_expiring_before_rescue_arrival_cannot_be_moved(dirty_result):
    # 备-07 在 11:30 过期，任何 11:35 才能到河西书院的接运车都无法承载该 10 份。
    full_backup = backup_truck(capacity=90, departure="2026-11-20T11:05:00+08:00", stops=[
        {"station": "河西书院", "eta": "2026-11-20T11:35:00+08:00"},
        {"station": "创客园", "eta": "2026-11-20T11:48:00+08:00"},
        {"station": "运动馆", "eta": "2026-11-20T12:05:00+08:00"},
    ])
    draft = rescue(dirty_result, backup=full_backup)
    row = pick(draft, "团-008")
    assert row["rescued_qty"] == 7 and row["undelivered_qty"] == 10
    assert row["code"] == "RESCUE_LOT_UNSAFE"
    assert all(move["lot"] != "备-07" for move in draft["moves"])
    assert draft["checks"]["freshness_ok"]


def test_window_arrival_at_cutoff_is_rejected(dirty_result):  # 半开窗口 [start,end)
    late = backup_truck(capacity=90, stops=[
        {"station": "创客园", "eta": "2026-11-20T11:58:00+08:00"},
        {"station": "运动馆", "eta": "2026-11-20T12:10:00+08:00"},
    ])
    draft = rescue(dirty_result, backup=late)
    assert pick(draft, "团-011")["code"] == "NO_RESCUE_TRUCK"


def test_failed_truck_and_rescue_truck_portions_and_undelivered(dirty_result):
    draft = rescue(dirty_result, backup=backup_truck())
    failed = next(v for v in draft["vehicles"] if v["role"] == "failed")
    helper = next(v for v in draft["vehicles"] if v["truck"] == "柿-04")
    backup_row = next(v for v in draft["vehicles"] if v["role"] == "backup")
    assert failed["original_loaded"] == 48
    assert failed["final_loaded"] == 0 and failed["undelivered"] == 29
    assert helper["rescued_loaded"] == 10 and helper["final_loaded"] == 10
    assert backup_row["final_loaded"] == 9
    totals = sum(v["final_loaded"] for v in draft["vehicles"]) + failed["undelivered"]
    assert totals == sum(v["loaded"] for v in dirty_result["allocation"]["vehicles"])
    assert draft["checks"]["fleet_total_conserved"]


def test_rescue_without_backup_uses_neighbor_spare_seats_only(dirty_result):
    draft = rescue(dirty_result, failed="柿-05")
    # 柿-06 只停芦港会堂，且 24 个余位足够接走 团-015 的 13 份；其余站点无车可救。
    assert pick(draft, "团-015")["rescued_qty"] == 13
    assert all(move["to_truck"] == "柿-06" for move in draft["moves"])
    assert pick(draft, "团-014")["code"] == "NO_RESCUE_TRUCK"
    assert draft["status"] == "MATCHED"


def test_unknown_and_empty_trucks_are_rejected(dirty_result):
    import pytest
    from app.errors import DomainError
    with pytest.raises(DomainError) as unknown:
        rescue(dirty_result, failed="幽灵车")
    assert unknown.value.code == "RESCUE_TRUCK_UNKNOWN"
    with pytest.raises(DomainError) as empty:
        rescue(dirty_result, failed="柿-04")  # 原车未装任何餐
    assert empty.value.code == "RESCUE_NOTHING"


def test_invalid_backup_is_rejected(dirty_result):
    import pytest
    from app.errors import DomainError
    with pytest.raises(DomainError) as error:
        rescue(dirty_result, backup=backup_truck(departure="2026-11-20T09:00:00+08:00"))
    assert error.value.code == "BACKUP_DEPARTED"
    with pytest.raises(DomainError) as dup:
        rescue(dirty_result, backup=backup_truck().__class__(backup_truck()) | {"truck": "柿-04"})
    assert dup.value.code == "BACKUP_DUPLICATE_ID"


def test_reconciliation_balance_blocks_nothing_when_books_match(dirty_result):
    draft = rescue(dirty_result, backup=backup_truck())
    assert draft["status"] == "MATCHED"
    for row in draft["orders"]:
        assert row["affected_qty"] == row["rescued_qty"] + row["undelivered_qty"]
        assert row["rescued_qty"] == sum(move["qty"] for move in row["moves"])
    for vehicle in draft["vehicles"]:
        if vehicle["role"] != "failed":
            assert vehicle["final_loaded"] <= vehicle["capacity"]


def test_full_coverage_when_backup_reaches_every_station_in_time(clean):
    result = evaluate(clean)
    target = result["allocation"]["vehicles"][0]
    stations = [stop["station"] for stop in target["stops"]]
    window_by_station = {(w["station"]): w for w in result["windows"]["rows"]}
    stops = [{"station": station, "eta": _iso(window_by_station[station]["start"] + 300)}
             for station in stations]
    backup = {"truck": "备-全", "wave": target["wave"], "capacity": target["capacity"],
              "departure": clean["trips"][0]["departure"], "stops": stops}
    draft = plan(result, target["truck"], instant(clean["at"]), backup)
    assert draft["checks"]["fully_covered"]
    assert sum(v["undelivered"] for v in draft["vehicles"]) == 0


def _iso(epoch):
    from app.clock import utc
    return utc(epoch)
