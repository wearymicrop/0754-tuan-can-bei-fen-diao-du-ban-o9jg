from app.pipeline import evaluate


def pick(result, key):
    return next(row for row in result['allocation']['rows'] if row['order']==key)


def test_locked_demands_precede_earlier_flexible_demands(dirty_result):  # TRAP-19
    locked, flexible=pick(dirty_result,'团-011'),pick(dirty_result,'团-001')
    assert locked['window']['end']>flexible['window']['end'] and locked['rank']==4<flexible['rank']==7
    assert [(row['meal'],row['qty']) for row in locked['loads']]==[('低敏餐',4),('低敏餐',5)]


def test_earliest_deadline_first_in_flexible_group(dirty_result):
    assert [pick(dirty_result,key)['rank'] for key in ('团-001','团-004','团-005')]==[7,8,9]


def test_earlier_expiry_used_only_if_safe_at_eta(dirty_result):
    row=pick(dirty_result,'团-008')
    assert [(item['lot'],item['qty'],item['substitution_line']) for item in row['loads']]==[('备-07',10,1),('备-01',7,1)]
    assert row['loads'][0]['arrival']=='2026-11-20T03:29:00Z'


def test_inventory_expiring_at_arrival_is_excluded(clean):
    clean['stock']=[{**clean['stock'][0],'expires':'2026-11-20T10:15:00+08:00'}]
    order=pick(evaluate(clean),'团-001')
    assert order['code']=='NO_VALID_STOCK' and order['short']==18


def test_no_transitive_allergy_substitution(clean):
    clean['stock']=[row for row in clean['stock'] if row['meal']=='小米羹']
    row=pick(evaluate(clean),'团-006')
    assert row['code']=='NO_VALID_STOCK' and row['short']==9


def test_repeated_stock_not_counted_twice(dirty_result):
    stage=dirty_result['allocation']
    assert stage['reasons']['STOCK_DUPLICATE']==1 and stage['reasons']['STOCK_CONFLICT']==2
    assert next(row for row in stage['stock'] if row['lot']=='备-08')['qty']==9


def test_disputed_order_never_books_vehicle(dirty_result):
    order=pick(dirty_result,'团-016')
    assert order['loads']==[] and order['disputed']==15 and order['shipped']==0
