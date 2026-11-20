from app.clock import instant
from app.records import group_by, integer, issue, token
from app.source import lines


def parse(record):
    raw = record['raw']
    if (not token(raw.get('meal')) or not integer(raw.get('qty'),1,100_000)
            or raw.get('kind') not in ('regular','spare')):
        raise ValueError('库存类型、餐品或份数无效')
    ready, expires = instant(raw.get('ready')), instant(raw.get('expires'))
    if ready >= expires:
        raise ValueError('库存就绪时间必须早于失效')
    return {**record,'kind':raw['kind'],'meal':raw['meal'],'qty':raw['qty'],'ready':ready,'expires':expires}


def register(source):
    cutoff = instant(source['at'])
    entries, rows, problems = [], [], []
    for record in lines(source,'stock'):
        raw = record['raw']
        if not token(raw.get('lot')):
            problems.append(issue(record,'STOCK_ID_INVALID','缺少批号，无法核量'))
            continue
        try:
            entries.append({**parse(record),'lot':raw['lot']})
        except ValueError:
            entries.append({**record,'lot':raw['lot'],'invalid':True})
            problems.append(issue(record,'STOCK_SCHEMA','批次餐品、时间或份数无效'))
    for (lot,),group in group_by(entries,'lot').items():
        complete = [row for row in group if not row.get('invalid')]
        signatures = {tuple(row[key] for key in ('qty','kind','meal','ready','expires')) for row in complete}
        if len(complete)!=len(group) or len(signatures)!=1:
            problems.extend(issue(row,'STOCK_CONFLICT','同一批号有互斥或缺失的库存事实') for row in group)
            spare = [row['raw'].get('qty') for row in group if row['raw'].get('kind') == 'spare'
                     and integer(row['raw'].get('qty'),1,100_000)]
            rows.append({**group[0],'lot':lot,'kind':'spare' if spare else 'unknown','qty':max(spare,default=0),
                         'status':'quarantined','left':0,'loaded':0})
            continue
        row = complete[0]
        expired = row['expires'] <= cutoff
        if expired:
            problems.append(issue(row,'STOCK_EXPIRED','此库存已过调度截点有效期'))
        problems.extend(issue(item,'STOCK_DUPLICATE','库存批号已采信') for item in complete[1:])
        rows.append({**row,'status':'expired' if expired else 'usable','left':0 if expired else row['qty'],'loaded':0})
    return rows, problems
