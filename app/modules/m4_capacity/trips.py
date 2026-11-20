from app.clock import instant, utc
from app.records import integer, token


def parse(record):
    raw = record['raw']
    truck, wave, cap, stops = (raw.get(key) for key in ('truck','wave','capacity','stops'))
    if (not token(truck) or not token(wave) or not integer(cap,1,100_000)
            or not isinstance(stops,list) or not 0 < len(stops) <= 100):
        raise ValueError('车辆或容量无效')
    depart=instant(raw.get('departure'))
    checked, seen, prior = [], set(), depart-1
    for stop in stops:
        if not isinstance(stop,dict) or not token(stop.get('station')) or stop['station'] in seen:
            raise ValueError('到站点无效或重复')
        eta=instant(stop.get('eta'))
        if not prior < eta <= depart+86400:
            raise ValueError('到站时序无效')
        prior=eta
        seen.add(stop['station'])
        checked.append({'station':stop['station'],'eta':eta,'arrival':utc(eta)})
    return {**record,'truck':truck,'wave':wave,'capacity':cap,'departure':depart,'stops':checked}
