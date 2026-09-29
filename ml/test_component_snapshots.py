import unittest
from types import SimpleNamespace
import pandas as pd
from ml.component_preprocess import features_at, build_component_snapshot_dataset
from ml.generate_service_data import DATE_COLUMNS
from unittest.mock import patch

class SnapshotBoundaries(unittest.TestCase):
    def setUp(self):
        self.t=pd.Timestamp('2024-02-05')
        self.c=SimpleNamespace(component_id='SUB-SIM-0001',machine_id='SIM-0001',affected_sub_assembly='SIM Test Unit',product_subsystem='SIM Test Subsystem',installation_date=pd.Timestamp('2024-01-01'),observation_end=pd.Timestamp('2025-06-24'))
        self.m=SimpleNamespace(installation_date=pd.Timestamp('2023-01-01'))
        self.w=pd.DataFrame([{'component_id':self.c.component_id,'created_date':self.t-pd.Timedelta(days=2),
            'investigated_on':self.t-pd.Timedelta(days=1),'resolved_on':self.t+pd.Timedelta(days=3),
            'closed_on':self.t+pd.Timedelta(days=4),'start_of_downtime':self.t-pd.Timedelta(days=2),
            'end_of_downtime':self.t+pd.Timedelta(days=3),'order_type':'Hardware Issue','problem_category':'SIM Warning',
            'severity':4,'resolution_code':'Part Replacement','total_downtime_hours':120,'order_status':'Closed'}])
    def test_future_resolution_and_downtime_do_not_leak(self):
        f=features_at(self.c,self.m,self.w,self.t)
        self.assertEqual(f['previous_replacement_count'],0)
        self.assertEqual(f['open_work_order_count'],1)
        self.assertEqual(f['historical_downtime_hours'],0)
        mutated=self.w.copy()
        mutated['resolution_code']='Adjustment / Repair'; mutated['total_downtime_hours']=99999
        mutated['order_status']='Created';mutated['closed_on']=self.t+pd.Timedelta(days=300)
        mutated['resolved_on']=self.t+pd.Timedelta(days=200);mutated['end_of_downtime']=self.t+pd.Timedelta(days=200)
        self.assertEqual(f,features_at(self.c,self.m,mutated,self.t))
    def test_known_outcomes_and_exact_time_excluded(self):
        w=self.w.copy();w['resolved_on']=self.t;w['end_of_downtime']=self.t
        self.assertEqual(features_at(self.c,self.m,w,self.t)['previous_service_count'],0)
        f=features_at(self.c,self.m,w,self.t+pd.Timedelta(seconds=1))
        self.assertEqual(f['previous_replacement_count'],1)
        self.assertEqual(f['historical_downtime_hours'],48)
    def test_non_reliability_orders_and_future_orders(self):
        w=self.w.copy();w['order_type']='Preventive Maintenance'
        f=features_at(self.c,self.m,w,self.t)
        self.assertEqual(f['errors_last_7_days'],0); self.assertEqual(f['non_reliability_orders_30d'],1)
        w['created_date']=self.t
        self.assertEqual(features_at(self.c,self.m,w,self.t)['previous_work_order_count'],0)
    def test_target_uses_resolution_not_creation_and_terminal(self):
        w=self.w.copy();w['resolved_on']=self.t+pd.Timedelta(days=30)
        components=pd.DataFrame([vars(self.c)]);machines=pd.DataFrame([{'machine_id':self.c.machine_id,'installation_date':self.m.installation_date}])
        with patch('ml.component_preprocess.load_component_data',return_value=(machines,components,w)):
            d=build_component_snapshot_dataset()
        self.assertEqual(d.loc[d.snapshot_time.eq(self.t),'replaced_within_30_days'].iloc[0],1)
        self.assertEqual(d.loc[d.snapshot_time.eq(self.t-pd.Timedelta(days=7)),'replaced_within_30_days'].iloc[0],0)
        self.assertTrue(d.snapshot_time.lt(w.resolved_on.iloc[0]).all())
        self.assertTrue((d.snapshot_time+pd.Timedelta(days=30)<=self.c.observation_end).all())

if __name__=='__main__':unittest.main()
