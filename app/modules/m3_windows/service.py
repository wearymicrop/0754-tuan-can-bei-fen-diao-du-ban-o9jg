from app.records import group_by, issue, report
from .contract import parse
from app.source import lines


def compile_windows(source, sections):
    entries, windows, disputed, problems = [], [], set(), []
    for record in lines(source,'windows'):
        try:
            entries.append(parse(record))
        except ValueError:
            problems.append(issue(record,'WINDOW_SCHEMA','站点、波次或交接时段无效'))
    for key,group in group_by(entries,'wave','station').items():
        if len({(row['start'],row['end']) for row in group}) > 1:
            disputed.add(key)
            problems.extend(issue(row,'WINDOW_CONFLICT','同波次、同站点存在互斥交接窗') for row in group)
        else:
            windows.append(group[0])
            problems.extend(issue(row,'WINDOW_DUPLICATE','交接窗重传') for row in group[1:])
    keyed = {(row['wave'],row['station']):row for row in windows}
    demands = []
    for order in sections['orders']['rows']:
        if order['state']=='cancelled':
            continue
        if order['state']=='conflict':
            demands.append({**order,'window':None,'dispute':'ORDER_CONFLICT'})
            continue
        key = order['wave'],order['station']
        actual = keyed.get(key)
        code = None if actual else 'WINDOW_CONFLICT' if key in disputed else 'WINDOW_MISSING'
        if code:
            problems.append(issue(order,code,'订单缺少唯一的到站窗口'))
        demands.append({**order,'window':actual,'dispute':code})
    demands.sort(key=lambda row:(row['window'] is None, row['window']['end'] if row['window'] else 0,row['order']))
    return report(windows,problems,demands=demands)
