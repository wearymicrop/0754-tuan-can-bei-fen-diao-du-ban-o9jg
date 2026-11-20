from app.clock import instant, utc
from app.records import token


def parse(record):
    raw = record['raw']
    wave, station = raw.get('wave'), raw.get('station')
    if not all(token(value) for value in (wave,station)):
        raise ValueError('缺少波次或站点')
    start,end = instant(raw.get('start')),instant(raw.get('end'))
    if not 0 < end-start <= 86400:
        raise ValueError('到站窗口无效')
    return {**record,'wave':wave,'station':station,'start':start,'end':end,'open_at':utc(start),'close_at':utc(end)}
