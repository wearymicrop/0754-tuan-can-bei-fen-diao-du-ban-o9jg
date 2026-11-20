from app.records import group_by, report
from .totals import tally


def reconcile(_source, sections):
    dispatch = sections['allocation']
    orders = dispatch['rows']
    totals, valid = tally(sections['windows']['demands'],orders,dispatch['stock'],dispatch['vehicles'])
    waves = []
    normalized = [{**row,'wave_label':row['wave'] if isinstance(row['wave'],str) and row['wave'] else '待确认'} for row in orders]
    for (wave,),rows in sorted(group_by(normalized,'wave_label').items()):
        amounts = {key:sum(row[key] for row in rows) for key in ('qty','shipped','short','disputed')}
        waves.append({'wave':wave,**amounts,'orders':len(rows)})
    issues = [item for section in ('orders','substitutions','windows','capacity','allocation') for item in sections[section]['issues']]
    return report(waves,issues,totals=totals,status='MATCHED' if valid else 'CHECK_REQUIRED')
