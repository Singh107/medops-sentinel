import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { bandForScore, resetReviewScroll, reviewRows, statusColors, type RiskSort, type RiskStatus } from './review';
import { Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler);

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001').replace(/\/$/, '');

type ComponentRow = {
  component_id: string;
  machine_id: string;
  part_type: string;
  errors_30d: number;
  service_attempts: number;
  replacement_risk: number;
  status: RiskStatus;
  total_events: number;
  replacements: number;
  replacement_flag: boolean;
};

type OverviewResponse = {
  service_events: number;
  components_tracked: number;
  high_risk_components: number;
  replacements: number;
  selected_model: string;
  components: ComponentRow[];
};

type ComponentDetail = {
  component_id: string;
  machine_id: string;
  part_type: string;
  component_age_days: number;
  age: number;
  machine_age_years: number;
  product_subsystem: string;
  system_status: 'Up' | 'Down';
  status_as_of: string;
  prediction_as_of: string;
  instance_status: string;
  historical_downtime_hours: number;
  replacement_risk: number;
  risk_label: RiskStatus;
  recommendation: string;
  risk_signals: Array<{ signal: string; weight: 'Low' | 'Moderate' | 'High' }>;
  errors: {
    last_7_days: number;
    last_30_days: number;
    last_90_days: number;
    critical_30d: number;
    unresolved: number;
    error_rate_change: number;
  };
  service_summary: {
    previous_service_attempts: number;
    service_attempts_30d: number;
    previous_replacements: number;
    recurring_same_problem_count: number;
    most_common_problem: string;
  };
  most_frequent_problem: string;
  previous_service_attempts: number;
  recent_problem_history: Array<{
    event_id: string;
    work_order_number: string;
    order_type: string;
    product_subsystem: string;
    affected_sub_assembly: string;
    system_status: string;
    order_status: string;
    total_downtime_hours: number | null;
    resolution_code: string | null;
    timestamp: string;
    problem_category: string;
    severity: number;
    resolved: boolean;
    service_performed: string | null;
    part_replaced: boolean;
  }>;
};

type AnalyticsResponse = {
  most_frequent_problem_categories: { category: string; count: number }[];
  replacement_frequency_by_component_type: { part_type: string; avg_risk: number; replacements: number }[];
  service_events_over_time: { period: string; count: number }[];
  component_type_counts: { part_type: string; count: number }[];
};

type ModelMetricsResponse = {
  selected_model: string;
  metrics: Record<string, any>;
  top_predictive_features: Array<{ feature: string; importance: number }>;
};

const formatPct = (value: number) => `${value.toFixed(1)}%`;

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}


const dateLabel = (value: string) => new Date(value.replace(' ', 'T')).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
const modelName = (value: string) => ({ logistic_regression: 'Logistic Regression', random_forest: 'Random Forest', naive_baseline: 'Majority baseline' }[value] ?? value.replace(/_/g, ' '));
const featureLabels: Record<string, string> = {
  service_attempts_30d: 'Completed resolutions - last 30 days',
  errors_last_7_days: 'Reliability orders - last 7 days', errors_last_30_days: 'Reliability orders - last 30 days',
  errors_last_90_days: 'Reliability orders - last 90 days', part_age_days: 'Subassembly age',
  machine_age_years: 'Machine age', unique_problem_types_30d: 'Distinct problems - last 30 days',
  critical_errors_30d: 'Critical reliability orders - last 30 days', days_since_last_error: 'Time since last reliability order',
  previous_service_count: 'Previous completed resolutions', previous_replacement_count: 'Previous replacements',
  recurring_same_problem_count: 'Recurring service pattern count', unresolved_problem_count: 'Open or deferred investigations',
  error_rate_change: 'Change in reliability order rate', previous_work_order_count: 'Previous work orders',
  work_orders_30d: 'Work orders - last 30 days', non_reliability_orders_30d: 'Other work orders - last 30 days',
  open_work_order_count: 'Open work orders', downtime_hours_30d: 'Completed downtime - last 30 days',
  historical_downtime_hours: 'Historical completed downtime', system_down_count_30d: 'Downtime starts - last 30 days',
  previous_repair_count: 'Previous repairs', previous_restart_count: 'Previous restarts',
};
function featureName(value: string) {
  const name = value.replace(/^(numeric|categorical)__/, '');
  for (const [prefix, label] of [['most_common_problem_type_', 'Recent common problem'], ['part_type_', 'Subassembly type'], ['product_subsystem_', 'Product subsystem']]) {
    if (name.startsWith(prefix)) return `${label}: ${name.slice(prefix.length).replace(/^SIM /, '')}`;
  }
  return featureLabels[name] ?? name.replace(/_/g, ' ');
}
function RiskBadge({ band }: { band: RiskStatus }) {
  return <span className="status-badge" style={{ color: statusColors[band], backgroundColor: `${statusColors[band]}18` }}>{band}</span>;
}
ChartJS.defaults.color = '#aabbd0';
ChartJS.defaults.borderColor = '#24374b';

export default function App() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [modelMetrics, setModelMetrics] = useState<ModelMetricsResponse | null>(null);
  const [selectedComponent, setSelectedComponent] = useState('');
  const [detail, setDetail] = useState<ComponentDetail | null>(null);
  const [error, setError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [search, setSearch] = useState('');
  const [band, setBand] = useState<RiskStatus | 'ALL'>('ALL');
  const [sort, setSort] = useState<RiskSort>('descending');
  const tableScroll = useRef<HTMLDivElement>(null);
  const detailScroll = useRef<HTMLElement>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetchJson<OverviewResponse>(`${API_BASE_URL}/api/overview`),
      fetchJson<AnalyticsResponse>(`${API_BASE_URL}/api/analytics`),
      fetchJson<ModelMetricsResponse>(`${API_BASE_URL}/api/model/metrics`),
    ]).then(([o, a, m]) => {
      if (!active) return;
      setOverview(o); setAnalytics(a); setModelMetrics(m);
      setSelectedComponent(reviewRows(o.components, '', 'ALL', 'descending')[0]?.component_id ?? '');
    }).catch(() => { if (active) setError('Unable to load the dashboard. Check that the MedOps backend is available on port 8001.'); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setDetail(null); setDetailError('');
    if (selectedComponent) {
      fetchJson<ComponentDetail>(`${API_BASE_URL}/api/components/${encodeURIComponent(selectedComponent)}`)
        .then(data => { if (active) setDetail(data); })
        .catch(() => { if (active) setDetailError('Unable to load this subassembly. Select another row or reload the page.'); });
    }
    return () => { active = false; };
  }, [selectedComponent]);

  const rows = useMemo(() => reviewRows(overview?.components ?? [], search, band, sort), [overview, search, band, sort]);
  useLayoutEffect(() => { resetReviewScroll(tableScroll.current); }, [rows]);
  useLayoutEffect(() => { resetReviewScroll(detailScroll.current); }, [selectedComponent, detail?.component_id]);

  if (error) return <main className="loading" role="alert"><h1>MedOps Sentinel</h1><p>{error}</p><button onClick={() => window.location.reload()}>Retry</button></main>;
  if (!overview || !analytics || !modelMetrics) return <main className="loading" role="status">Loading MedOps Sentinel...</main>;
  const metrics = modelMetrics.metrics?.[modelMetrics.selected_model]?.selected_threshold;
  const riskSummary = analytics.replacement_frequency_by_component_type ?? [];
  const selectedHidden = selectedComponent && !rows.some(c => c.component_id === selectedComponent);
  const chartOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } } as const;

  return <main className="page-shell">
    <header className="topbar">
      <div><p className="eyebrow">MEDOPS SENTINEL</p><h1>Service &amp; Component Intelligence</h1>
        <p className="subtitle">Surface recurring service patterns and identify subassemblies that warrant engineering review.</p></div>
      <span className="pill">Synthetic Data <span aria-hidden="true">&bull;</span> Decision-Support Prototype</span>
    </header>
    <section className="kpis" aria-label="Fleet summary">
      {[
        ['Subassemblies tracked', overview.components_tracked], ['High-risk reviews', overview.high_risk_components],
        ['Historical replacements', overview.replacements], ['Work orders analyzed', overview.service_events],
      ].map(([label, value]) => <article className="card kpi-card" key={label}><p className="kpi-label">{label}</p><strong className="kpi-value">{Number(value).toLocaleString('en-US')}</strong></article>)}
    </section>

    <section className="equipment-grid" aria-label="Engineering review workspace">
      <div className="card table-card">
        <div className="section-header"><div><p className="eyebrow">REVIEW WORKSPACE</p><h2>Subassembly Review</h2><p className="muted">Select a subassembly to inspect its historical score and service records.</p></div></div>
        <div className="table-controls">
          <label className="search-control">Search<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Subassembly, machine or ID" /></label>
          <label>Risk band<select value={band} onChange={e => setBand(e.target.value as RiskStatus | 'ALL')}><option value="ALL">All bands</option><option value="HIGH RISK">High Risk</option><option value="MONITOR">Monitor</option><option value="LOW RISK">Low Risk</option></select></label>
          <label>Risk score<select value={sort} onChange={e => setSort(e.target.value as RiskSort)}><option value="descending">Highest first</option><option value="ascending">Lowest first</option></select></label>
        </div>
        <div className="table-summary"><span aria-live="polite">{rows.length} of {overview.components_tracked} subassemblies</span><button className="text-button" onClick={() => { setSearch(''); setBand('ALL'); setSort('descending'); resetReviewScroll(tableScroll.current); }}>Reset filters</button></div>
        <div ref={tableScroll} className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable subassembly review table">
          <table><thead><tr><th>Affected subassembly</th><th>Machine</th><th className="number">Reliability<br />orders (30d)</th><th className="number">Completed<br />resolutions (30d)</th><th className="number" aria-sort={sort === 'descending' ? 'descending' : 'ascending'}>Historical<br />risk score</th><th>Risk band</th></tr></thead>
            <tbody>{rows.map((c, index) => <tr key={c.component_id} className={selectedComponent === c.component_id ? 'selected-row' : ''} onClick={() => setSelectedComponent(c.component_id)}>
              <td><button className="row-button" aria-pressed={selectedComponent === c.component_id} onClick={() => setSelectedComponent(c.component_id)}>{c.part_type}<span className="row-id">#{index + 1} &middot; {c.component_id}</span></button></td>
              <td className="nowrap">{c.machine_id}</td><td className="number">{c.errors_30d}</td><td className="number">{c.service_attempts}</td><td className="number risk-cell">{formatPct(c.replacement_risk)}</td><td><RiskBadge band={c.status} /></td>
            </tr>)}</tbody>
          </table>
          {rows.length === 0 && <p className="empty-state">No subassemblies match these filters. Try a different search or reset the filters.</p>}
        </div>
        <p className="table-note">Fleet KPIs include all subassemblies; table filters do not change them. Row numbers show position in the current sort. Each score is the instance's last eligible historical assessment, including replaced instances. Display bands: Low Risk &lt;40%, Monitor 40&ndash;&lt;70%, High Risk &ge;70%; these are not the model's binary evaluation threshold.</p>
      </div>

      <aside ref={detailScroll} className="card machine-card" aria-label="Selected subassembly details" aria-busy={!!selectedComponent && !detail && !detailError}>
        {selectedHidden && <p className="selection-note">Selected {selectedComponent} is outside the current filters.</p>}
        {detailError ? <p role="alert">{detailError}</p> : !detail ? <p role="status">{selectedComponent ? `Loading ${selectedComponent}...` : 'Select a subassembly to review.'}</p> : <>
          <div className="detail-context"><strong>{detail.component_id}</strong><span aria-label={`Historical risk score ${formatPct(detail.replacement_risk)}`} style={{ color: statusColors[detail.risk_label] }}>{formatPct(detail.replacement_risk)}</span><RiskBadge band={detail.risk_label} /></div>
          <header className="detail-heading"><h2>{detail.part_type}</h2><div className="metadata"><span>{detail.product_subsystem}</span><span className="nowrap">{detail.machine_id}</span></div></header>
          <div className="risk-overview"><div><strong className="risk-value" style={{ color: statusColors[detail.risk_label] }}>{formatPct(detail.replacement_risk)}</strong><p className="mini-label">Historical replacement risk score</p></div><RiskBadge band={detail.risk_label} /></div>
          <p className="recommendation">{detail.recommendation}</p>
          <p className="muted">Scored {dateLabel(detail.prediction_as_of)}. An uncalibrated model score, not a confirmed probability or a maintenance instruction.</p>
          <dl className="metadata-grid"><div><dt>Instance</dt><dd>{detail.instance_status}</dd></div><div><dt>Subassembly age at score</dt><dd>{detail.age.toFixed(2)} years</dd></div><div><dt>Machine age at export</dt><dd>{detail.machine_age_years.toFixed(2)} years</dd></div><div><dt>System at export</dt><dd>{detail.system_status} <small>{dateLabel(detail.status_as_of)}</small></dd></div></dl>
          <section className="detail-panel-block"><h3>Why it's flagged</h3><p className="muted">Historical context for review; these signals are not causal explanations.</p><ul className="signal-list">{detail.risk_signals.map(signal => <li key={signal.signal}><span className="signal-marker" aria-hidden="true" />{signal.signal}</li>)}</ul></section>
          <section className="detail-panel-block"><h3>Service history at assessment</h3><dl className="metadata-grid"><div><dt>Reliability orders (7d)</dt><dd>{detail.errors.last_7_days}</dd></div><div><dt>Critical reliability orders (30d)</dt><dd>{detail.errors.critical_30d}</dd></div><div><dt>Completed resolutions</dt><dd>{detail.previous_service_attempts}</dd></div><div><dt>Previous replacements</dt><dd>{detail.service_summary.previous_replacements}</dd></div><div className="full-width"><dt>Most common recent problem</dt><dd>{detail.service_summary.most_common_problem}</dd></div></dl></section>
          <section className="detail-panel-block"><div className="section-header"><h3>Recent work orders</h3><span className="muted">Latest {Math.min(detail.recent_problem_history.length, 8)}</span></div>
            <p className="muted">Full recorded history; may include events after the score date. Total recorded completed downtime: {detail.historical_downtime_hours.toFixed(1)} h.</p>
            <div className="history-list">{detail.recent_problem_history.slice(0, 8).map(event => <article key={event.event_id} className="history-item">
              <div className="history-heading"><strong>{event.work_order_number}</strong><time dateTime={event.timestamp.replace(' ', 'T')}>{dateLabel(event.timestamp)}</time></div>
              <div className="chips"><span className="chip">{event.order_type}</span><span className="chip">Severity {event.severity}</span><span className="chip">System {event.system_status} at creation</span></div>
              <p className="history-problem">{event.problem_category}</p><div className="metadata"><span>{event.product_subsystem}</span><span>{event.affected_sub_assembly}</span></div>
              <div className="history-footer"><span>{event.order_status}</span><span>{event.total_downtime_hours === null ? 'Downtime incomplete' : `${event.total_downtime_hours.toFixed(1)} h downtime`}</span></div>
              <div className="resolution"><span>Resolution</span><strong>{event.resolution_code ?? 'Awaiting resolution'}</strong></div>
            </article>)}</div>
            {!detail.recent_problem_history.length && <p className="empty-state">No recorded work orders.</p>}
          </section>
        </>}
      </aside>
    </section>

    <section className="analysis-grid" aria-label="Historical fleet context">
      <article className="card chart-card"><h2>Work Orders Over Time</h2><p className="muted">Monthly synthetic service activity across the observed fleet.</p><div className="chart-frame"><Line aria-label="Monthly work order counts" role="img" options={chartOptions} data={{ labels: analytics.service_events_over_time.map(p => p.period), datasets: [{ label: 'Work orders', data: analytics.service_events_over_time.map(p => p.count), borderColor: '#60a5fa', backgroundColor: '#60a5fa18', fill: true, tension: .2, pointRadius: 1.5 }] }} /></div></article>
      <article className="card chart-card"><h2>Historical Risk Scores by Subassembly Type</h2><p className="muted">Mean of last historical scores. Colors follow the display bands.</p><div className="chart-frame"><Bar aria-label="Average historical risk scores by subassembly type" role="img" data={{ labels: riskSummary.map(r => r.part_type), datasets: [{ label: 'Mean historical risk score (%)', data: riskSummary.map(r => r.avg_risk), backgroundColor: riskSummary.map(r => statusColors[bandForScore(r.avg_risk)]), borderRadius: 3 }] }} options={{ ...chartOptions, indexAxis: 'y', scales: { x: { min: 0, max: 100, ticks: { callback: value => `${value}%` } }, y: { grid: { display: false }, ticks: { font: { size: 10 } } } } }} /></div><p className="chart-legend">Low Risk &lt;40% <span aria-hidden="true">/</span> Monitor 40&ndash;&lt;70% <span aria-hidden="true">/</span> High Risk &ge;70%</p></article>
    </section>

    <section className="card methodology"><p className="eyebrow">MODEL &amp; METHODOLOGY</p><div className="section-header"><h2>Synthetic prototype model</h2><span className="chip">Temporal holdout</span></div>
      <div className="method-summary"><div><span className="mini-label">Model</span><strong>{modelName(modelMetrics.selected_model)}</strong></div><div><span className="mini-label">Prediction target</span><strong>Part Replacement resolution within the next 30 days</strong></div></div>
      {metrics ? <dl className="metric-strip">{[['Precision', 'precision'], ['Recall', 'recall'], ['F1', 'f1'], ['ROC-AUC', 'roc_auc'], ['PR-AUC (AP)', 'pr_auc']].map(([label, key]) => <div key={key}><dt>{label}</dt><dd>{typeof metrics[key] === 'number' ? formatPct(metrics[key] * 100) : 'Unavailable'}</dd></div>)}</dl> : <p>Metrics unavailable.</p>}
      <p className="muted">Temporal holdout: 71 weekly snapshots, including 18 positive cases.</p>
      <p className="muted">Metrics are from a small synthetic temporal holdout and are not evidence of real-world medical-device performance. Weekly historical assessments use only information available before the prediction cutoff.</p>
      <details><summary>Signals associated with model output</summary><p className="muted">Largest reported feature weights. Associations do not establish causes of replacement.</p><ul className="feature-list">{modelMetrics.top_predictive_features.slice(0, 5).map(item => <li key={item.feature}><span>{featureName(item.feature)}</span><span className="feature-weight">{item.importance.toFixed(3)}</span></li>)}</ul></details>
    </section>
    <footer>All equipment, work orders, and identifiers shown are synthetic. Historical decision support for engineering review; not clinical software or real-time monitoring.</footer>
  </main>;
}
