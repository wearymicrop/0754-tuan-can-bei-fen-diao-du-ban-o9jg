from app.modules.m6_reconcile.totals import tally
from app.pipeline import evaluate


def test_dirty_totals_match(dirty_result):
    result=dirty_result['reconcile']
    assert result['status']=='MATCHED'
    assert result['totals']=={'requested':228,'shipped':158,'short':42,'disputed':28,'difference':0,'orders':19,
        'vehicle_capacity':210,'spare':{'declared':93,'used':33,'left':40,'expired':11,'quarantined':9,'difference':0}}


def test_clean_all_portions_shipped(clean_result):
    totals=clean_result['reconcile']['totals']
    assert totals['requested']==totals['shipped']==222 and totals['spare']['left']==63


def test_wave_totals_aggregate_to_batch(dirty_result):
    result=dirty_result['reconcile']
    assert [row['shipped'] for row in result['rows']]==[48,44,66]
    assert sum(row['shipped'] for row in result['rows'])==result['totals']['shipped']


def test_empty_orders_require_review(clean):  # TRAP-18
    clean['orders']=[]
    result=evaluate(clean)['reconcile']
    assert result['status']=='CHECK_REQUIRED' and result['totals']['requested']==0


def test_unbalanced_allocation_fails_despite_matching_demand():
    demands=[{'order':'010','qty':3}]
    outputs=[{'order':'010','qty':3,'shipped':3,'short':0,'disputed':0,'loads':[{'truck':'甲','lot':'01','qty':3}]}]
    stock=[{'lot':'01','kind':'regular','status':'usable','qty':3,'loaded':3,'left':0}]
    trucks=[{'truck':'甲','loaded':3,'capacity':2}]
    totals,valid=tally(demands,outputs,stock,trucks)
    assert totals['difference']==0 and not valid


def test_spare_consumption_equals_allocated_loads(dirty_result):
    loads=[load for row in dirty_result['allocation']['rows'] for load in row['loads'] if load['kind']=='spare']
    assert sum(load['qty'] for load in loads)==dirty_result['reconcile']['totals']['spare']['used']==33
