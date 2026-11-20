from app.pipeline import evaluate


def test_dirty_missing_stop_is_disputed(dirty_result):
    demands=dirty_result['windows']['demands']
    row=next(row for row in demands if row['order']=='团-019')
    assert (row['dispute'],row['qty'])==('WINDOW_MISSING',7)


def test_cancellation_not_a_shipment_demand(dirty_result):
    assert '团-010' not in {row['order'] for row in dirty_result['windows']['demands']}


def test_equivalent_windows_are_deduped(dirty_result):
    stage=dirty_result['windows']
    assert len(stage['rows'])==9 and stage['reasons']['WINDOW_DUPLICATE']==1


def test_arrival_at_cutoff_is_not_on_time(dirty_result):  # TRAP-23
    row=next(row for row in dirty_result['capacity']['rows'] if row['truck']=='柿-04')
    assert [stop['on_time'] for stop in row['stops']]==[True,False]


def test_multiple_windows_same_wave_quarantine_orders(clean):  # TRAP-25
    clean['windows'].append({**clean['windows'][0],'end':'2026-11-20T10:40:00+08:00'})
    result=evaluate(clean)['windows']
    assert result['reasons']['WINDOW_CONFLICT']==4
    assert [row['order'] for row in result['demands'] if row['dispute']=='WINDOW_CONFLICT']==['团-001','团-002']


def test_orders_use_only_window_of_order_wave(clean):
    clean['windows'][0]['wave']='另一波次'
    result=evaluate(clean)['windows']
    assert result['reasons']=={'WINDOW_MISSING':2}
