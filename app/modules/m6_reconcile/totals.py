from collections import Counter


def tally(demands, outcomes, stock, vehicles):
    load_trucks, load_lots = Counter(), Counter()
    order_consistent = {row['order']:row['qty'] for row in demands} == {row['order']:row['qty'] for row in outcomes}
    order_consistent &= len(outcomes)==len({row['order'] for row in outcomes})
    for row in outcomes:
        order_consistent &= row['qty']==row['shipped']+row['short']+row['disputed']
        order_consistent &= row['shipped']==sum(load['qty'] for load in row['loads'])
        for load in row['loads']:
            load_trucks[load['truck']] += load['qty']
            load_lots[load['lot']] += load['qty']
    trucks_ok = all(0 <= item['loaded'] == load_trucks[item['truck']] <= item['capacity'] for item in vehicles)
    lots_ok = all(item['loaded']==load_lots[item['lot']] and
                  (item['status']!='usable' or item['qty']==item['loaded']+item['left']) for item in stock)
    trucks_ok &= set(load_trucks) <= {item['truck'] for item in vehicles}
    lots_ok &= set(load_lots) <= {item['lot'] for item in stock}
    sent = sum(row['shipped'] for row in outcomes)
    short = sum(row['short'] for row in outcomes)
    disputed = sum(row['disputed'] for row in outcomes)
    requested = sum(row['qty'] for row in demands)
    spare = [row for row in stock if row['kind']=='spare']
    reserve = {'declared':sum(row['qty'] for row in spare),'used':sum(row['loaded'] for row in spare),
               'left':sum(row['left'] for row in spare),'expired':sum(row['qty'] for row in spare if row['status']=='expired'),
               'quarantined':sum(row['qty'] for row in spare if row['status']=='quarantined')}
    reserve['difference'] = reserve['declared']-sum(reserve[key] for key in ('used','left','expired','quarantined'))
    totals = {'requested':requested,'shipped':sent,'short':short,'disputed':disputed,'difference':requested-sent-short-disputed,
              'orders':len(demands),'vehicle_capacity':sum(row['capacity'] for row in vehicles),'spare':reserve}
    return totals, bool(demands) and order_consistent and lots_ok and trucks_ok and not totals['difference'] and not reserve['difference']
