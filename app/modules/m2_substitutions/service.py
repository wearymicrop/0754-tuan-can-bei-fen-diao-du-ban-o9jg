from app.records import issue, report, token
from app.source import lines
from .graph import cyclic_meals


def approve(source, _):
    edges, problems = {}, []
    for record in lines(source,'substitutions'):
        start, target = (record['raw'].get(key) for key in ('requested','spare'))
        if not all(token(value) for value in (start,target)):
            problems.append(issue(record,'SUBSTITUTION_SCHEMA','替代餐品字段缺失'))
            continue
        if (start,target) in edges:
            problems.append(issue(record,'SUBSTITUTION_DUPLICATE','替代边重复'))
            continue
        edges[start,target] = {**record,'requested':start,'spare':target}
    blocked = cyclic_meals(edges)
    output = []
    for (start,target), row in edges.items():
        if start in blocked or target in blocked:
            problems.append(issue({**row,'cycle_meals':blocked.get(start,blocked.get(target))},
                                  'SUBSTITUTION_CYCLE','该替代边涉及循环餐品'))
        else:
            output.append(row)
    return report(output,problems,cycle_meals=sorted(blocked))
