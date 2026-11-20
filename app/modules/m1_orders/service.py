from app.clock import instant
from app.records import group_by, issue, report, token
from app.source import lines
from .revisions import conservative_qty, fingerprint, parse


def resolve(source, _):
    as_of = instant(source['at'])
    items, output, problems = [], [], []
    for record in lines(source,'orders'):
        raw = record['raw']
        ident = raw.get('order')
        if not token(ident):
            problems.append(issue(record,'ORDER_ID_INVALID','订单号缺失'))
            continue
        try:
            if instant(raw.get('issued')) > as_of:
                problems.append(issue(record,'FUTURE_REVISION','改签尚未到调度截点'))
                continue
            items.append({**parse(record),'order':ident,'invalid':False})
        except ValueError:
            items.append({**record,'order':ident,'invalid':True})
            problems.append(issue(record,'ORDER_SCHEMA','改签字段或时间无效'))
    for group in group_by(items,'order').values():
        good = [row for row in group if not row['invalid']]
        malformed = any(row['invalid'] for row in group)
        accepted = None
        blocking = None
        for (revision,), rows in sorted(group_by(good,'revision').items()):
            if len({fingerprint(row) for row in rows}) != 1:
                problems.extend(issue(row,'ORDER_REVISION_CONFLICT','同一改签版本存在互斥值') for row in rows)
                blocking = rows[0]
                break
            first = rows[0]
            problems.extend(issue(row,'ORDER_DUPLICATE','同一改签版本重复提交') for row in rows[1:])
            if (first['supersedes'] != (accepted['revision'] if accepted else None)
                    or revision != (accepted['revision'] + 1 if accepted else 1)
                    or (accepted and first['t'] < accepted['t'])):
                problems.append(issue(first,'BROKEN_REVISION_CHAIN','改签缺上版或提交时间倒退'))
                blocking = first
                break
            accepted = first
        conflict = malformed or blocking is not None
        basis = accepted or blocking or group[0]
        qty = accepted['qty'] if accepted else conservative_qty(group)
        raw = basis['raw']
        row = {key:basis.get(key, raw.get(key)) for key in ('order','revision','meal','station','wave','locked','table','line','raw')}
        output.append({**row,'qty':qty,'state':'conflict' if conflict else accepted['status'],
                       'revision_lines':[item['line'] for item in group]})
    output.sort(key=lambda row: row['order'])
    return report(output,problems,input_count=len(source['orders']))
