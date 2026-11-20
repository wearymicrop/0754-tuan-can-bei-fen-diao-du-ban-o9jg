from app.pipeline import evaluate


def test_planned_capacity_from_six_vehicles(dirty_result):
    result=dirty_result['capacity']
    assert result['total_capacity']==210 and len(result['rows'])==6


def test_repeated_trip_has_only_one_capacity(dirty_result):
    assert dirty_result['capacity']['reasons']['TRUCK_DUPLICATE']==1
    assert [row['capacity'] for row in dirty_result['capacity']['rows'] if row['truck']=='柿-01']==[44]


def test_overlapping_stops_are_isolated(clean):
    clean['trips'][0]['stops'][1]['eta']=clean['trips'][0]['stops'][0]['eta']
    result=evaluate(clean)['capacity']
    assert result['reasons']=={'TRIP_SCHEMA':1} and result['total_capacity']==266


def test_conflicting_truck_capacities_quarantined(clean):
    clean['trips'].append({**clean['trips'][0],'capacity':95})
    result=evaluate(clean)['capacity']
    assert result['reasons']=={'TRUCK_CONFLICT':2} and result['total_capacity']==266


def test_departure_cannot_precede_run_cutoff(clean):
    clean['trips'][0]['departure']='2026-11-20T08:59:00+08:00'
    assert evaluate(clean)['capacity']['reasons']=={'DEPARTED':1}


def test_trip_capacity_summed_across_stops(dirty_result):
    stage=dirty_result['allocation']
    truck=stage['vehicles'][0]
    loads=[load for row in stage['rows'] for load in row['loads'] if load['truck']==truck['truck']]
    assert sum(load['qty'] for load in loads)==44==truck['capacity']
    assert {load['station'] for load in loads}=={'北门诊厅','市民服务站'}
