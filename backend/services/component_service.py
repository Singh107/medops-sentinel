from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from backend.database.db import get_connection
ROOT=Path(__file__).resolve().parents[2]


def _table(name):
    with get_connection() as conn: return pd.read_sql_query(f'SELECT * FROM {name}',conn)


def _risk_band(risk):
    return 'HIGH RISK' if risk>=.7 else 'MONITOR' if risk>=.4 else 'LOW RISK'


def _recommendation_for_risk(risk):
    return 'Elevated replacement risk; review recommended.' if risk>=.4 else 'Continue monitoring.'


def _risk_signals_for_snapshot(s):
    signals=[]
    for key,text in [('errors_last_30_days','reliability work orders in the last 30 days'),
                     ('unresolved_problem_count','open or previously deferred investigations'),
                     ('recurring_same_problem_count','occurrences of a recurring service pattern')]:
        if s[key]>0: signals.append({'signal':f'{int(s[key])} {text}', 'weight':'Moderate'})
    if s['downtime_hours_30d']>0:
        signals.append({'signal':f"{s['downtime_hours_30d']:.1f} completed downtime hours in the last 30 days",'weight':'Moderate'})
    return signals or [{'signal':'No material historical warning signals at this prediction date','weight':'Low'}]


def _latest():
    return _table('component_snapshots').sort_values('snapshot_time').groupby('component_id').tail(1).set_index('component_id')


def get_machines():
    return _table('machines').to_dict('records')


def get_components():
    components=_table('components'); machines=_table('machines').set_index('machine_id')
    orders=_table('work_orders'); latest=_latest(); result=[]
    for c in components.itertuples(index=False):
        s=latest.loc[c.component_id]; m=machines.loc[c.machine_id]; own=orders[orders.component_id.eq(c.component_id)]
        replacements=int(own.resolution_code.eq('Part Replacement').sum())
        result.append({'component_id':c.component_id,'machine_id':c.machine_id,
          'top_level_serial_number':m.top_level_serial_number,'part_type':c.affected_sub_assembly,
          'affected_sub_assembly':c.affected_sub_assembly,'product_subsystem':c.product_subsystem,
          'component_age_days':int(s.part_age_days),'age':float(s.part_age_days/365.25),
          'machine_age_years':float(m.age),'system_status':m.system_status,'status_as_of':m.status_as_of,
          'prediction_as_of':s.snapshot_time,'errors_30d':int(s.errors_last_30_days),
          'service_attempts':int(s.service_attempts_30d),'replacement_risk':round(float(s.risk_probability)*100,1),
          'status':_risk_band(s.risk_probability),'total_events':len(own),'work_order_count':len(own),
          'historical_downtime_hours':float(own.total_downtime_hours.sum()),'replacements':replacements,
          'replacement_flag':bool(replacements),'instance_status':'Replaced' if replacements else 'Observed'})
    return result


def get_overview():
    components=get_components(); metrics=get_model_metrics()
    return {'service_events':sum(c['work_order_count'] for c in components),'components_tracked':len(components),
            'high_risk_components':sum(c['status']=='HIGH RISK' for c in components),
            'replacements':sum(c['replacements'] for c in components),'selected_model':metrics['selected_model'],'components':components}


def get_component_events(component_id):
    with get_connection() as conn:
        rows=conn.execute('''SELECT w.*,c.machine_id,c.product_subsystem,c.affected_sub_assembly
                            FROM work_orders w JOIN components c USING(component_id)
                            WHERE w.component_id=? ORDER BY w.created_date DESC''',(component_id,)).fetchall()
    result=[]
    for row in rows:
        w=dict(row)
        w.update({'event_id':w['work_order_number'],'timestamp':w['created_date'],
                  'part_replaced':w['resolution_code']=='Part Replacement',
                  'resolved':bool(w['resolved_on'] and w['resolution_code']!='Issue Logged for Further Investigation'),
                  'service_performed':w['resolution_code']})
        result.append(w)
    return result


def get_component_risk(component_id):
    latest=_latest()
    if component_id not in latest.index: raise ValueError('Subassembly not found')
    s=latest.loc[component_id]; risk=float(s.risk_probability)
    return {'component_id':component_id,'replacement_risk':round(risk*100,1),'risk_label':_risk_band(risk),
            'prediction_as_of':s.snapshot_time,'recommendation':_recommendation_for_risk(risk),
            'risk_signals':_risk_signals_for_snapshot(s),'explanatory_factors':[]}


def get_component_detail(component_id):
    matches=[c for c in get_components() if c['component_id']==component_id]
    if not matches: raise ValueError('Subassembly not found')
    c=matches[0]; s=_latest().loc[component_id]
    return {**c,**get_component_risk(component_id),
            'errors':{'last_7_days':int(s.errors_last_7_days),'last_30_days':int(s.errors_last_30_days),
                      'last_90_days':int(s.errors_last_90_days),'critical_30d':int(s.critical_errors_30d),
                      'unresolved':int(s.unresolved_problem_count),'error_rate_change':float(s.error_rate_change)},
            'service_summary':{'previous_service_attempts':int(s.previous_service_count),'service_attempts_30d':int(s.service_attempts_30d),
                               'previous_replacements':int(s.previous_replacement_count),'recurring_same_problem_count':int(s.recurring_same_problem_count),
                               'most_common_problem':s.most_common_problem_type},
            'most_frequent_problem':s.most_common_problem_type,'previous_service_attempts':int(s.previous_service_count),
            'recent_problem_history':get_component_events(component_id)[:20]}


def get_analytics():
    components=pd.DataFrame(get_components()); orders=_table('work_orders')
    orders['period']=pd.to_datetime(orders.created_date).dt.strftime('%Y-%m')
    problems=orders.problem_category.value_counts().head(8)
    return {'most_frequent_problem_categories':[{'category':k,'count':int(v)} for k,v in problems.items()],
            'replacement_frequency_by_component_type':[{'part_type':k,'avg_risk':round(float(g.replacement_risk.mean()),1),
                                                        'replacements':int(g.replacements.sum())} for k,g in components.groupby('part_type')],
            'service_events_over_time':[{'period':k,'count':len(g)} for k,g in orders.groupby('period')],
            'component_type_counts':[{'part_type':k,'count':len(g)} for k,g in components.groupby('part_type')]}


def get_model_metrics():
    metrics=json.loads((ROOT/'models'/'component_metrics.json').read_text())
    return {k:metrics[k] for k in ['selected_model','selected_threshold','metrics','top_predictive_features']}
