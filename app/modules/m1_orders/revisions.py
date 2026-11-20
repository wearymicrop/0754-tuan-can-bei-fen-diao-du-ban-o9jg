from app.clock import instant
from app.records import integer, token


def parse(record):
    data = record['raw']
    rev, prior = data.get('revision'), data.get('supersedes')
    qty, status = data.get('qty'), data.get('status')
    if ('supersedes' not in data or not integer(rev, 1, 5000) or (prior is not None and not integer(prior, 1, 5000))
            or not integer(qty, maximum=10000) or status not in ('active','cancelled')
            or (status == 'cancelled') != (qty == 0) or type(data.get('locked')) is not bool
            or not all(token(data.get(key)) for key in ('meal','station','wave'))):
        raise ValueError('改签字段无效')
    return {**record, 't':instant(data.get('issued')),
            **{key:data[key] for key in ('revision','supersedes','qty','status','locked','meal','station','wave')}}


def fingerprint(row):
    return tuple(row[key] for key in ('t','supersedes','qty','status','locked','meal','station','wave'))


def conservative_qty(records):
    return max((row['raw'].get('qty') for row in records if integer(row['raw'].get('qty'),maximum=10000)), default=0)
