from app.modules.m1_orders.service import resolve


def by_id(result,number):
    return next(row for row in result['rows'] if row['order']==number)


def test_revision_sorted_even_when_row_arrives_first(dirty_result):  # TRAP-13
    row=by_id(dirty_result['orders'],'团-004')
    assert (row['revision'],row['qty'],row['revision_lines']) == (2,21,[1,5])


def test_conflicting_revision_preserves_previous_count(dirty_result):  # TRAP-14
    row=by_id(dirty_result['orders'],'团-016')
    assert (row['revision'],row['qty'],row['state']) == (1,15,'conflict')
    assert dirty_result['orders']['reasons']['ORDER_REVISION_CONFLICT']==2


def test_cancellation_replaces_prior_count(dirty_result):
    row=by_id(dirty_result['orders'],'团-010')
    assert (row['revision'],row['qty'],row['state'])==(2,0,'cancelled')


def test_duplicate_at_utc_same_second(dirty_result):  # TRAP-11
    row=by_id(dirty_result['orders'],'团-002')
    assert len(row['revision_lines'])==2 and dirty_result['orders']['reasons']['ORDER_DUPLICATE']==1


def test_future_revision_is_ignored(dirty_result):
    row=by_id(dirty_result['orders'],'团-018')
    assert (row['qty'],row['revision'])==(8,1) and dirty_result['orders']['reasons']['FUTURE_REVISION']==1


def test_stale_chain_is_disputed(dirty_result):
    row=by_id(dirty_result['orders'],'团-020')
    assert row['qty']==6 and row['state']=='conflict'
    assert dirty_result['orders']['reasons']['BROKEN_REVISION_CHAIN']==1


def test_incomplete_order_keeps_declared_quantity(clean):  # TRAP-07
    clean['orders'][0].pop('supersedes')
    result=resolve(clean,{})
    assert by_id(result,'团-001')['qty']==18 and by_id(result,'团-001')['state']=='conflict'
