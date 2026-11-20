from app.records import issue, report
from .dispatch import assign
from .stock import register

DETAIL = {'NO_ON_TIME_TRUCK':'没有能在窗口内抵达的车辆','TRUCK_FULL':'满足窗口的车辆已满载',
          'NO_VALID_STOCK':'缺少有效期内且符合餐品要求的库存','ORDER_CONFLICT':'待核验订单版本',
          'WINDOW_MISSING':'站点缺少到站窗口','WINDOW_CONFLICT':'站点窗口有冲突'}


def allocate(source, sections):
    stock, problems = register(source)
    trips = sections['capacity']['rows']
    results, remaining = assign(sections['windows']['demands'],trips,stock,sections['substitutions']['rows'])
    for row in results:
        if row['code']:
            problems.append(issue(row,row['code'],DETAIL[row['code']]))
    vehicles = [{**row,'remaining':remaining[row['truck']],'loaded':row['capacity']-remaining[row['truck']]} for row in trips]
    return report(results,problems,stock=stock,vehicles=vehicles)
