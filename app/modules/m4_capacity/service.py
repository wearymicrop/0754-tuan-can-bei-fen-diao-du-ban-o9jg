from app.clock import instant
from app.records import group_by, issue, report
from app.source import lines
from .trips import parse


def plan(source, sections):
    cutoff = instant(source['at'])
    entries, trips, problems = [], [], []
    for record in lines(source,'trips'):
        try:
            row = parse(record)
        except ValueError:
            problems.append(issue(record,'TRIP_SCHEMA','车次、容量或到站序列无效'))
            continue
        if row['departure'] < cutoff:
            problems.append(issue(row,'DEPARTED','车辆已在批次截点前出发'))
            continue
        entries.append(row)
    for group in group_by(entries,'truck').values():
        signatures = {(row['wave'],row['capacity'],row['departure'],tuple((stop['station'],stop['eta']) for stop in row['stops'])) for row in group}
        if len(signatures) > 1:
            problems.extend(issue(row,'TRUCK_CONFLICT','同一车辆收到互斥班次或容量') for row in group)
            continue
        trips.append(group[0])
        problems.extend(issue(row,'TRUCK_DUPLICATE','车次已采信') for row in group[1:])
    windows = {(row['wave'],row['station']):row for row in sections['windows']['rows']}
    for trip in trips:
        for stop in trip['stops']:
            window = windows.get((trip['wave'],stop['station']))
            stop['on_time'] = bool(window and window['start'] <= stop['eta'] < window['end'])
            if not stop['on_time']:
                problems.append(issue({**trip,'stop':stop['station']},'STOP_OUTSIDE_WINDOW','车次到站超窗或站点缺窗'))
    return report(trips,problems,total_capacity=sum(row['capacity'] for row in trips))
