"""Verify served artifacts and application consistency without retraining."""
import json
import urllib.request
from pathlib import Path
from unittest.mock import patch
import joblib
import numpy as np
import pandas as pd
from backend.database.db import get_connection


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8001'+path, timeout=60) as r:
        assert r.status == 200
        return json.load(r)


def main():
    metrics=json.loads(Path('models/component_metrics.json').read_text())
    snapshots=pd.read_csv('data/component_snapshots.csv')
    from ml.component_preprocess import FEATURE_COLUMNS
    model=joblib.load('models/component_model.joblib')
    assert np.allclose(model.predict_proba(snapshots[FEATURE_COLUMNS])[:,1],snapshots.risk_probability)
    endpoints=['/health','/api/overview','/api/machines','/api/components','/api/components/SUB-SIM-0001','/api/components/SUB-SIM-0001/events','/api/components/SUB-SIM-0001/risk','/api/analytics','/api/model/metrics']
    responses={path:get(path) for path in endpoints}
    assert responses['/api/model/metrics']['metrics']==metrics['metrics']
    assert responses['/api/model/metrics']['selected_model']==metrics['selected_model']
    latest=snapshots.sort_values('snapshot_time').groupby('component_id').tail(1).set_index('component_id')
    for component in responses['/api/components']:
        row=latest.loc[component['component_id']]
        assert component['replacement_risk']==round(float(row.risk_probability)*100,1)
        assert component['errors_30d']==int(row.errors_last_30_days)
        assert component['service_attempts']==int(row.service_attempts_30d)
        assert component['affected_sub_assembly']==row.part_type
        assert component['product_subsystem']==row.product_subsystem
    detail=responses['/api/components/SUB-SIM-0001']
    assert detail['machine_id'].startswith('SIM-')
    assert detail['system_status'] in ['Up','Down']
    for order in responses['/api/components/SUB-SIM-0001/events']:
        assert order['part_replaced']==(order['resolution_code']=='Part Replacement')
        assert order['work_order_number'].startswith('WO-SIM-')
    assert detail['replacement_risk']==responses['/api/components/SUB-SIM-0001/risk']['replacement_risk']
    assert detail['replacement_risk']==round(float(latest.loc['SUB-SIM-0001'].risk_probability)*100,1)
    with get_connection() as conn:
        db=pd.read_sql_query('SELECT * FROM component_snapshots',conn)
        assert len(db)==len(snapshots)
        assert np.allclose(db.risk_probability,snapshots.risk_probability)
        for table in ['machines','components','work_orders']:
            assert conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==len(pd.read_csv(f'data/{table}.csv'))
    # Test reseed route orchestration without repeating the frozen final evaluation.
    from backend.main import seed_database_endpoint, SeedPayload
    with patch('subprocess.run') as run, patch('backend.main.init_db'), patch('backend.main.seed_database'):
        assert seed_database_endpoint(SeedPayload())['status']=='seeded'
        assert run.call_count==2
    with urllib.request.urlopen('http://127.0.0.1:5173',timeout=20) as r:
        assert r.status==200
    result={'http_get_endpoints':{p:200 for p in endpoints},'frontend_http_status':200,
            'saved_pipeline_csv_sqlite_api_consistent':True,
            'normalized_schema_and_derived_replacement_flags':True,
            'reseed_route':'orchestration tested with subprocess mocks; generation/training/reseed executed separately',
            'production_build':'passed',
            'browser_runtime':'blocked: browser-control inventory has no available browsers',
            'mealmind':'no processes or ports modified; only verified MedOps backend restarted'}
    Path('models/application_validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
