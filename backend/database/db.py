"""SQLite mirror of normalized synthetic raw tables and derived ML snapshots."""
import sqlite3
from pathlib import Path
import pandas as pd
DB_PATH=Path(__file__).resolve().parents[2]/'data'/'medops.db'
DATA_DIR=DB_PATH.parent


def get_connection():
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    DATA_DIR.mkdir(exist_ok=True)


def seed_database():
    # One transaction prevents APIs observing a partially migrated operational dataset.
    frames={name:pd.read_csv(DATA_DIR/f'{name}.csv',keep_default_na=True) for name in ['machines','components','work_orders','component_snapshots']}
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        obj=conn.execute("SELECT type FROM sqlite_master WHERE name='service_events'").fetchone()
        if obj: conn.execute(f"DROP {obj['type'].upper()} service_events")
        for name in ['component_snapshots','work_orders','components','machines']:
            conn.execute(f'DROP TABLE IF EXISTS {name}')
        for name,frame in frames.items():
            columns=[f'"{c}" '+('REAL' if pd.api.types.is_numeric_dtype(frame[c]) else 'TEXT') for c in frame.columns]
            if name=='machines':
                columns+=['PRIMARY KEY(machine_id)','UNIQUE(top_level_serial_number)',"CHECK(system_status IN ('Up','Down'))"]
            elif name=='components':
                columns+=['PRIMARY KEY(component_id)','FOREIGN KEY(machine_id) REFERENCES machines(machine_id)','UNIQUE(machine_id,affected_sub_assembly)']
            elif name=='work_orders':
                columns+=['PRIMARY KEY(work_order_number)','FOREIGN KEY(component_id) REFERENCES components(component_id)',"CHECK(system_status IN ('Up','Down'))"]
            else:
                columns+=['PRIMARY KEY(component_id,snapshot_time)','FOREIGN KEY(component_id) REFERENCES components(component_id)']
            conn.execute(f'CREATE TABLE {name} ('+','.join(columns)+')')
            clean=frame.astype(object).where(pd.notna(frame),None)
            conn.executemany(f'INSERT INTO {name} VALUES ('+','.join('?' for _ in frame.columns)+')',clean.itertuples(index=False,name=None))
        conn.execute('CREATE INDEX work_orders_component_date ON work_orders(component_id,created_date)')
        # Compatibility view only: no independently stored service-event outcomes.
        conn.execute('''CREATE VIEW service_events AS
          SELECT w.work_order_number AS event_id,c.machine_id,w.component_id,w.created_date AS timestamp,
                 w.problem_category,w.severity,w.resolution_code AS service_performed,
                 CASE WHEN w.resolved_on IS NOT NULL AND w.resolution_code!='Issue Logged for Further Investigation' THEN 1 ELSE 0 END AS resolved,
                 CASE WHEN w.resolution_code='Part Replacement' THEN 1 ELSE 0 END AS part_replaced
          FROM work_orders w JOIN components c USING(component_id)''')
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()


def reset_db():
    init_db(); seed_database()
