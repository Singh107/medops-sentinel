"""Wholly fictional operational records; no external records or text sources."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
MACHINE_COUNT = 36
COMPONENTS_PER_MACHINE = 8
OBSERVATION_DAYS = 540
# A fictional taxonomy, not a description of any actual device architecture.
HIERARCHY = {
    'SIM Thermal Subsystem': ['SIM Circulation Unit', 'SIM Flow Monitor'],
    'SIM Image Subsystem': ['SIM Image Controller', 'SIM Processing Unit'],
    'SIM Energy Subsystem': ['SIM Power Unit', 'SIM Regulation Unit'],
    'SIM Motion Subsystem': ['SIM Position Drive', 'SIM Alignment Monitor'],
    'SIM Software Subsystem': ['SIM Control Application', 'SIM Configuration Service'],
    'SIM Network Subsystem': ['SIM Network Interface', 'SIM Message Gateway'],
}
SUBASSEMBLY_TYPES = {name: subsystem for subsystem, names in HIERARCHY.items() for name in names}
ORDER_TYPES = ['Maintenance Issue', 'Hardware Issue', 'Software Issue', 'Feature Request',
               'Preventive Maintenance', 'Configuration Issue', 'User / Training Issue']
RELIABILITY_TYPES = ['Maintenance Issue', 'Hardware Issue', 'Software Issue']
RESOLUTIONS = ['Part Replacement', 'Reboot / Restart', 'Adjustment / Repair', 'Software Update',
               'Configuration Change', 'User Retraining', 'Issue Logged for Further Investigation',
               'No Fault Found', 'Preventive Service Completed']
PROBLEMS = ['SIM Intermittent Warning', 'SIM Response Drift', 'SIM Availability Warning', 'SIM Repeated Reset']
DATE_COLUMNS = ['created_date', 'investigated_on', 'resolved_on', 'closed_on', 'start_of_downtime', 'end_of_downtime']


def sigmoid(value):
    return 1.0 / (1.0 + np.exp(-value))


def generate_machines():
    rng = np.random.default_rng(101)
    return pd.DataFrame([{'machine_id': f'SIM-{i+1:04d}', 'top_level_serial_number': f'SIM-{i+1:04d}',
                          'model': f'SIM-MODEL-{i%4+1:02d}',
                          'installation_date': pd.Timestamp('2021-01-01')+pd.Timedelta(days=i*18+int(rng.integers(0,35)))}
                         for i in range(MACHINE_COUNT)])


def generate_components(machines):
    rng = np.random.default_rng(202)
    rows = []
    for machine in machines.itertuples(index=False):
        # Unique machine + subassembly type; instance ID survives every historical join.
        for name in rng.choice(list(SUBASSEMBLY_TYPES), COMPONENTS_PER_MACHINE, replace=False):
            install = machine.installation_date + pd.Timedelta(days=int(rng.integers(30,420)))
            rows.append({'component_id': f'SUB-SIM-{len(rows)+1:04d}', 'machine_id': machine.machine_id,
                         'affected_sub_assembly': name, 'product_subsystem': SUBASSEMBLY_TYPES[name],
                         'installation_date': install, 'observation_end': install+pd.Timedelta(days=OBSERVATION_DAYS)})
    return pd.DataFrame(rows)


def generate_work_orders(machines, components):
    rng = np.random.default_rng(303)
    machine_dates = machines.set_index('machine_id').installation_date
    rows = []
    for c in components.itertuples(index=False):
        latent = rng.normal(0, 1)
        own = []
        next_available = c.installation_date
        for offset in range(OBSERVATION_DAYS):
            day = c.installation_date+pd.Timedelta(days=offset)
            # One active work order per subassembly; multiple may overlap on a machine.
            if day < next_available:
                continue
            recent = [w for w in own if w['created_date'] >= day-pd.Timedelta(days=45) and w['order_type'] in RELIABILITY_TYPES]
            failures = sum(w['resolution_code']=='Issue Logged for Further Investigation' for w in own)
            critical = sum(w['severity'] >= 4 for w in recent)
            recurrence = max([sum(w['problem_category']==p for w in recent) for p in PROBLEMS], default=0)
            age_factor = offset/OBSERVATION_DAYS
            issue_signal = -5.7+.9*latent+.45*age_factor+1.2*len(recent)+critical+.9*recurrence+.55*len(own)+.6*failures+rng.normal(0,.4)
            if rng.random() >= np.clip(sigmoid(issue_signal), .02, .28):
                continue
            weights = np.array([.25,.30,.16,.06,.10,.08,.05])
            if c.product_subsystem in ['SIM Software Subsystem','SIM Network Subsystem']:
                weights = np.array([.13,.12,.35,.10,.08,.15,.07])
            kind = rng.choice(ORDER_TYPES,p=weights)
            reliability = kind in RELIABILITY_TYPES
            severity = int(rng.integers(3,6) if reliability and (len(recent)>=4 or critical) else rng.integers(1,4))
            if not reliability:
                severity = min(severity,2)
            created = day+pd.Timedelta(hours=int(rng.integers(0,24)))
            if created >= c.observation_end:
                continue
            investigated = created+pd.Timedelta(hours=float(rng.uniform(1,24)))
            proposed_resolution = investigated+pd.Timedelta(hours=float(np.clip(rng.lognormal(2.5+.15*severity,.8),2,240)))
            proposed_close = proposed_resolution+pd.Timedelta(hours=float(rng.uniform(1,36)))
            p_replace = sigmoid(-4.2+.60*age_factor+.30*min(len(recent)/4,1)+.35*min(critical/2,1)
                                +.45*min(failures/2,1)+.40*min(recurrence/2,1)+.30*min(len(own)/6,1)
                                +.35*min(failures/3,1)+.15+latent+rng.normal(0,1))
            # Preventive/training/feature work does not become a reliability event by definition.
            if kind in ['Feature Request','Preventive Maintenance','User / Training Issue']:
                p_replace = 0
            elif kind in ['Software Issue','Configuration Issue']:
                p_replace *= .20  # uncommon hardware intervention, still possible
            if rng.random() < p_replace:
                resolution = 'Part Replacement'
            elif kind == 'Preventive Maintenance':
                resolution = 'Preventive Service Completed'
            elif kind == 'Feature Request':
                resolution = 'Issue Logged for Further Investigation'
            elif kind == 'User / Training Issue':
                resolution = rng.choice(['User Retraining','No Fault Found'])
            elif kind == 'Configuration Issue':
                resolution = rng.choice(['Configuration Change','Reboot / Restart','No Fault Found'])
            elif kind == 'Software Issue':
                resolution = rng.choice(['Software Update','Reboot / Restart','Configuration Change','Issue Logged for Further Investigation'])
            else:
                resolution = rng.choice(['Adjustment / Repair','Reboot / Restart','No Fault Found','Issue Logged for Further Investigation'],p=[.45,.15,.15,.25])
            down_prob = sigmoid(-3+.65*severity+.3*latent+rng.normal(0,.5)) if reliability else .04
            if kind == 'Feature Request':
                down_prob = 0
            down = rng.random()<down_prob
            start = created if down else pd.NaT
            # Open downtime has a start but no invented future end/total.
            end = proposed_resolution if down and proposed_resolution<c.observation_end else pd.NaT
            resolved = proposed_resolution if proposed_resolution<c.observation_end else pd.NaT
            closed = proposed_close if proposed_close<c.observation_end else pd.NaT
            investigated = investigated if investigated<c.observation_end else pd.NaT
            known_resolution = resolution if pd.notna(resolved) else None
            status = 'Closed' if pd.notna(closed) else 'Resolved' if pd.notna(resolved) else 'Investigating' if pd.notna(investigated) else 'Created'
            problem = rng.choice(PROBLEMS) if reliability else f'SIM {kind}'
            row = {'work_order_number':f'WO-SIM-{len(rows)+1:06d}', 'component_id':c.component_id,
                   'created_date':created, 'investigated_on':investigated, 'resolved_on':resolved, 'closed_on':closed,
                   'order_type':kind, 'subject':f'Synthetic {kind.lower()} for {c.affected_sub_assembly}',
                   'description':f'Synthetic example: {problem.lower()} recorded for review.',
                   'investigation_description':f'Synthetic inspection: reviewed {problem.lower()}.' if pd.notna(investigated) else None,
                   'resolution_description':f'Synthetic outcome: {known_resolution}.' if known_resolution else None,
                   'system_status':'Down' if down else 'Up', 'order_status':status, 'record_type':'Synthetic Service Work Order',
                   'problem_category':problem, 'severity':severity, 'resolution_code':known_resolution,
                   'start_of_downtime':start, 'end_of_downtime':end,
                   'total_downtime_hours':(end-start).total_seconds()/3600 if pd.notna(end) else (None if down else 0.0),
                   'time_to_close':(closed-created).total_seconds()/3600 if pd.notna(closed) else None,
                   'age':(created-machine_dates[c.machine_id]).total_seconds()/(86400*365.25)}
            rows.append(row); own.append(row)
            next_available = proposed_close
            if known_resolution == 'Part Replacement':
                break
    return pd.DataFrame(rows)


def generate_dataset():
    machines = generate_machines(); components = generate_components(machines)
    orders = generate_work_orders(machines, components)
    # Static export status explicitly has an as-of date, never an ML input.
    machines['status_as_of'] = machines.machine_id.map(components.groupby('machine_id').observation_end.max())
    machines['age'] = (machines.status_as_of-machines.installation_date).dt.total_seconds()/(86400*365.25)
    joined = orders.merge(components[['component_id','machine_id','observation_end']],on='component_id')
    # Work-order system status means the whole machine at creation, including
    # outages caused by another subassembly's overlapping order.
    for _, group in joined.groupby('machine_id'):
        outages = group[group.start_of_downtime.notna()]
        for idx, work in group.iterrows():
            down = ((outages.start_of_downtime <= work.created_date) &
                    (outages.end_of_downtime.isna() | (outages.end_of_downtime > work.created_date))).any()
            orders.loc[idx, 'system_status'] = 'Down' if down else 'Up'
    def status(row):
        w=joined[joined.machine_id.eq(row.machine_id)]
        return 'Down' if ((w.start_of_downtime<=row.status_as_of)&(w.end_of_downtime.isna()|(w.end_of_downtime>row.status_as_of))).any() else 'Up'
    machines['system_status'] = machines.apply(status,axis=1)
    return machines,components,orders


def main():
    DATA_DIR.mkdir(exist_ok=True)
    for name, frame in zip(['machines','components','work_orders'],generate_dataset()):
        frame.to_csv(DATA_DIR/f'{name}.csv',index=False)
        print(f'{name}: {len(frame)}')

if __name__=='__main__': main()
