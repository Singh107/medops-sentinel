"""Independent schema/feature audit for synthetic operational work orders."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from ml.component_preprocess import load_component_data, FEATURE_COLUMNS, features_at
from ml.component_model import _split_chronological
from ml.generate_service_data import SUBASSEMBLY_TYPES, RELIABILITY_TYPES, ORDER_TYPES, RESOLUTIONS


def main():
    machines,components,orders=load_component_data()
    assert np.allclose(machines.age,(machines.status_as_of-machines.installation_date).dt.total_seconds()/(86400*365.25))
    dated=orders.merge(components[['component_id','machine_id']],on='component_id').merge(machines[['machine_id','installation_date']],on='machine_id')
    assert np.allclose(dated.age,(dated.created_date-dated.installation_date).dt.total_seconds()/(86400*365.25))
    for column in ['subject','description','investigation_description','resolution_description']:
        assert orders[column].dropna().str.startswith('Synthetic').all()
    assert 'part_replaced' not in pd.read_csv('data/work_orders.csv',nrows=0).columns
    snapshots=pd.read_csv('data/component_snapshots.csv',parse_dates=['snapshot_time'])
    assert machines.machine_id.is_unique and machines.top_level_serial_number.is_unique
    assert machines.machine_id.str.fullmatch(r'SIM-\d{4}').all()
    assert components.component_id.str.fullmatch(r'SUB-SIM-\d{4}').all()
    assert orders.work_order_number.str.fullmatch(r'WO-SIM-\d{6}').all()
    assert orders.work_order_number.is_unique and components.component_id.is_unique
    assert not components.duplicated(['machine_id','affected_sub_assembly']).any()
    assert set(components.machine_id)<=set(machines.machine_id)
    assert set(orders.component_id)<=set(components.component_id)
    assert components.apply(lambda c:SUBASSEMBLY_TYPES[c.affected_sub_assembly]==c.product_subsystem,axis=1).all()
    assert orders.order_type.isin(ORDER_TYPES).all()
    assert orders.resolution_code.dropna().isin(RESOLUTIONS).all()
    assert orders.part_replaced.eq(orders.resolution_code.eq('Part Replacement').astype(int)).all()
    assert (orders.resolved_on.notna()==orders.resolution_code.notna()).all()
    for a,b in [('created_date','investigated_on'),('investigated_on','resolved_on'),('resolved_on','closed_on')]:
        known=orders[b].notna();assert orders.loc[known,a].notna().all();assert (orders.loc[known,b]>=orders.loc[known,a]).all()
    closed=orders.closed_on.notna()
    assert orders.loc[closed,'order_status'].eq('Closed').all()
    assert orders.loc[~closed,'time_to_close'].isna().all()
    assert np.allclose(orders.loc[closed,'time_to_close'],(orders.loc[closed,'closed_on']-orders.loc[closed,'created_date']).dt.total_seconds()/3600)
    no_down=orders.start_of_downtime.isna();complete=orders.end_of_downtime.notna();ongoing=~no_down&~complete
    assert orders.loc[no_down,'end_of_downtime'].isna().all() and orders.loc[no_down,'total_downtime_hours'].eq(0).all()
    assert orders.loc[ongoing,'total_downtime_hours'].isna().all()
    assert (orders.loc[complete,'end_of_downtime']>=orders.loc[complete,'start_of_downtime']).all()
    assert np.allclose(orders.loc[complete,'total_downtime_hours'],(orders.loc[complete,'end_of_downtime']-orders.loc[complete,'start_of_downtime']).dt.total_seconds()/3600)
    assert not snapshots.duplicated(['component_id','snapshot_time']).any()
    assert snapshots.snapshot_time.dt.dayofweek.eq(0).all()
    assert snapshots.sort_values('snapshot_time').groupby('component_id').snapshot_time.diff().dropna().eq(pd.Timedelta(days=7)).all()
    machine_map=machines.set_index('machine_id')
    checked=0
    for c in components.itertuples(index=False):
        own=orders[orders.component_id.eq(c.component_id)].sort_values('created_date')
        assert (own.created_date>=c.installation_date).all() and (own.created_date<c.observation_end).all()
        replacements=own.loc[own.resolution_code.eq('Part Replacement'),'resolved_on']
        assert len(replacements)<=1
        if len(replacements):assert own.created_date.lt(replacements.min()).all()
        for _,s in snapshots[snapshots.component_id.eq(c.component_id)].iterrows():
            t=s.snapshot_time;start30=t-pd.Timedelta(days=30)
            assert t>=c.installation_date and t+pd.Timedelta(days=30)<=c.observation_end
            assert replacements.empty or t<replacements.min()
            assert s.replaced_within_30_days==int(((replacements>t)&(replacements<=t+pd.Timedelta(days=30))).any())
            # Independent plain-record reconstruction rather than calling the feature builder.
            h=[w for w in own.to_dict('records') if w['created_date']<t]
            rel=[w for w in h if w['order_type'] in RELIABILITY_TYPES]
            known=[w for w in h if pd.notna(w['resolved_on']) and w['resolved_on']<t]
            win={n:[w for w in rel if w['created_date']>=t-pd.Timedelta(days=n)] for n in [7,30,90]}
            modes=Counter(w['problem_category'] for w in win[30]);most=sorted(modes,key=lambda p:(-modes[p],p))[0] if modes else 'No recent problem'
            dt=[w for w in h if pd.notna(w['end_of_downtime']) and w['end_of_downtime']<t]
            expected={'part_type':c.affected_sub_assembly,'product_subsystem':c.product_subsystem,
              'part_age_days':(t-c.installation_date).days,'machine_age_years':(t-machine_map.loc[c.machine_id,'installation_date']).total_seconds()/(86400*365.25),
              **{f'errors_last_{n}_days':len(w) for n,w in win.items()},
              'unique_problem_types_30d':len(modes),'critical_errors_30d':sum(w['severity']>=4 for w in win[30]),
              'days_since_last_error':(t-max(w['created_date'] for w in rel)).days if rel else 999,
              'previous_service_count':len(known),'service_attempts_30d':sum(w['resolved_on']>=start30 for w in known),
              'previous_replacement_count':sum(w['resolution_code']=='Part Replacement' for w in known),
              'recurring_same_problem_count':max(Counter(w['problem_category'] for w in rel).values(),default=0),
              'unresolved_problem_count':len(h)-len(known)+sum(w['resolution_code']=='Issue Logged for Further Investigation' for w in known),
              'error_rate_change':(sum(w['created_date']>=t-pd.Timedelta(days=15) for w in rel)-sum(start30<=w['created_date']<t-pd.Timedelta(days=15) for w in rel))/15,
              'most_common_problem_type':most,'previous_work_order_count':len(h),
              'work_orders_30d':sum(w['created_date']>=start30 for w in h),
              'non_reliability_orders_30d':sum(w['created_date']>=start30 and w['order_type'] not in RELIABILITY_TYPES for w in h),
              'open_work_order_count':len(h)-len(known),
              'downtime_hours_30d':sum(max(0,(w['end_of_downtime']-max(w['start_of_downtime'],start30)).total_seconds()/3600) for w in dt),
              'historical_downtime_hours':sum((w['end_of_downtime']-w['start_of_downtime']).total_seconds()/3600 for w in dt),
              'system_down_count_30d':sum(pd.notna(w['start_of_downtime']) and start30<=w['start_of_downtime']<t for w in h),
              'previous_repair_count':sum(w['resolution_code']=='Adjustment / Repair' for w in known),
              'previous_restart_count':sum(w['resolution_code']=='Reboot / Restart' for w in known)}
            assert set(expected)==set(FEATURE_COLUMNS)
            for name,value in expected.items():
                assert s[name]==value if isinstance(value,str) else np.isclose(s[name],value), (c.component_id,t,name)
            checked+=1
    # Mutate unknown future fields and future work orders at sampled prediction dates.
    for _,s in snapshots.sample(min(100,len(snapshots)),random_state=91).iterrows():
        c=components[components.component_id.eq(s.component_id)].iloc[0];m=machine_map.loc[c.machine_id];t=s.snapshot_time
        own=orders[orders.component_id.eq(s.component_id)].copy(); before=features_at(c,m,own,t)
        future=own.resolved_on.isna()|own.resolved_on.ge(t)
        own.loc[future,'resolution_code']='No Fault Found';own.loc[future,'resolved_on']=t+pd.Timedelta(days=500)
        unknown_end=own.end_of_downtime.isna()|own.end_of_downtime.ge(t)
        own.loc[unknown_end,'end_of_downtime']=t+pd.Timedelta(days=500)
        own['closed_on']=t+pd.Timedelta(days=700);own['total_downtime_hours']=99999;own['order_status']='Created'
        own['investigation_description']='Synthetic changed future text';own['resolution_description']='Synthetic changed future text'
        own=own[own.created_date<t]
        assert before==features_at(c,m,own,t)
    parts=_split_chronological(snapshots)
    for l,r in zip(parts,parts[1:]):
        assert l.snapshot_time.max()+pd.Timedelta(days=30)<r.snapshot_time.min()
        assert not set(l.loc[l.replaced_within_30_days.eq(1),'component_id']) & set(r.loc[r.replaced_within_30_days.eq(1),'component_id'])
    # Machine operational status includes outages from all linked subassemblies.
    joined=orders.merge(components[['component_id','machine_id']],on='component_id')
    for _,g in joined.groupby('machine_id'):
        dt=g[g.start_of_downtime.notna()]
        for w in g.itertuples(index=False):
            expected='Down' if ((dt.start_of_downtime<=w.created_date)&(dt.end_of_downtime.isna()|(dt.end_of_downtime>w.created_date))).any() else 'Up'
            assert w.system_status==expected
    result={'all_checks_passed':True,'snapshots_checked':checked,'features_per_snapshot':len(FEATURE_COLUMNS),
            'future_mutation_checks':100,'orders_checked':len(orders),'open_orders':int(orders.closed_on.isna().sum()),
            'ongoing_downtime':int(ongoing.sum()),'source_of_truth':'resolution_code == Part Replacement at resolved_on',
            'checks':['keys and hierarchy','age and timestamps','lifecycle','downtime arithmetic','strict historical feature availability',
                      'future resolution target','terminal instances','weekly cadence','complete follow-up','temporal embargo','machine status transitions']}
    Path('models/leakage_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
