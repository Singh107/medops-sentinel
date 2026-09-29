// Read-only QA against the existing API. No ML execution or database writes.
// Run from frontend: node scripts/qa-review.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const code = ts.transpileModule(readFileSync(new URL('../src/review.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const exports = {};
vm.runInNewContext(code, { exports });
const { reviewRows, bandForScore, resetReviewScroll, statusColors } = exports;
const api = async path => {
  const response = await fetch(`http://localhost:8001${path}`);
  assert.equal(response.status, 200, path);
  return response.json();
};
const paths = ['/health', '/api/overview', '/api/machines', '/api/components',
  '/api/components/SUB-SIM-0001', '/api/components/SUB-SIM-0001/events',
  '/api/components/SUB-SIM-0001/risk', '/api/analytics', '/api/model/metrics'];
const responses = await Promise.all(paths.map(api));
const overview = responses[1];
const rows = overview.components;
const original = JSON.stringify(rows);
const ascending = reviewRows(rows, '', 'ALL', 'ascending');
const descending = reviewRows(rows, '', 'ALL', 'descending');
assert.equal(ascending[0].replacement_risk, Math.min(...rows.map(c => c.replacement_risk)));
assert.equal(descending[0].replacement_risk, Math.max(...rows.map(c => c.replacement_risk)));
assert.equal(descending.length, rows.length);
assert.equal(JSON.stringify(rows), original, 'Sorting must not mutate API state');
for (let i = 1; i < rows.length; i++) {
  assert.ok(descending[i - 1].replacement_risk >= descending[i].replacement_risk);
  assert.ok(ascending[i - 1].replacement_risk <= ascending[i].replacement_risk);
}
for (const band of ['LOW RISK', 'MONITOR', 'HIGH RISK']) {
  const filtered = reviewRows(rows, '', band, 'descending');
  assert.ok(filtered.every(c => c.status === band && bandForScore(c.replacement_risk) === band));
  assert.equal(filtered.length, rows.filter(c => bandForScore(c.replacement_risk) === band).length);
  const reversed = reviewRows(rows, '', band, 'ascending');
  if (filtered.length) {
    assert.equal(filtered[0].replacement_risk, Math.max(...filtered.map(c => c.replacement_risk)));
    assert.equal(reversed[0].replacement_risk, Math.min(...filtered.map(c => c.replacement_risk)));
  }
}
assert.equal(overview.high_risk_components, rows.filter(c => c.replacement_risk >= 70).length);
assert.equal(overview.high_risk_components, reviewRows(rows, '', 'HIGH RISK', 'descending').length);
for (const [score, expected] of [[0, 'LOW RISK'], [39.9, 'LOW RISK'], [40, 'MONITOR'], [69.9, 'MONITOR'], [70, 'HIGH RISK'], [100, 'HIGH RISK']]) {
  assert.equal(bandForScore(score), expected);
}
assert.equal(statusColors['LOW RISK'], '#22c55e');
assert.equal(statusColors.MONITOR, '#f59e0b');
assert.equal(statusColors['HIGH RISK'], '#f87171');
const found = reviewRows(rows, '  sub-sim-0131  ', 'ALL', 'descending');
assert.equal(found.length, 1);
assert.equal(found[0].component_id, 'SUB-SIM-0131');
assert.equal(reviewRows(rows, 'SUB-SIM-0131', 'HIGH RISK', 'descending').length, 0);
assert.equal(reviewRows(rows, 'no-such-component-xyz', 'ALL', 'descending').length, 0);
const fixture = [9, 80, 100].map((score, i) => ({ component_id: String(i), machine_id: 'M', part_type: 'P', status: bandForScore(score), replacement_risk: score }));
assert.equal(reviewRows(fixture, '', 'ALL', 'descending')[0].replacement_risk, 100);
const scroll = { scrollTop: 9000, scrollLeft: 50 };
resetReviewScroll(scroll);
assert.equal(scroll.scrollTop, 0);
assert.equal(scroll.scrollLeft, 50);
resetReviewScroll(null);

for (const selected of [descending[0], ascending[0], found[0]]) {
  const base = `/api/components/${selected.component_id}`;
  const [detail, risk, events] = await Promise.all([api(base), api(`${base}/risk`), api(`${base}/events`)]);
  assert.equal(detail.component_id, selected.component_id);
  assert.equal(detail.replacement_risk, selected.replacement_risk);
  assert.equal(risk.replacement_risk, selected.replacement_risk);
  assert.equal(detail.risk_label, selected.status);
  assert.equal(detail.prediction_as_of, selected.prediction_as_of);
  assert.deepEqual(detail.recent_problem_history, events.slice(0, 20));
  for (const field of ['part_type', 'product_subsystem', 'machine_id', 'recommendation']) assert.ok(detail[field]);
}
const metrics = responses[8].metrics[responses[8].selected_model].selected_threshold;
assert.deepEqual(metrics.confusion_matrix, [[15, 38], [0, 18]], 'Published 71/18 holdout context');
assert.equal((metrics.precision * 100).toFixed(1), '32.1');
assert.equal((metrics.recall * 100).toFixed(1), '100.0');
assert.equal((metrics.f1 * 100).toFixed(1), '48.6');
assert.equal((metrics.roc_auc * 100).toFixed(1), '65.9');
assert.equal((metrics.pr_auc * 100).toFixed(1), '32.1');
assert.equal((await fetch('http://localhost:5173')).status, 200);
console.log(JSON.stringify({
  status: 'passed', applicationGETRoutes: paths.length, vehicles: rows.length,
  highRisk: overview.high_risk_components, maximum: descending[0].replacement_risk,
  minimum: ascending[0].replacement_risk,
  screenshotSequencePositions: descending.flatMap((c, i) => [53.8, 53.2, 53.0, 52.9].includes(c.replacement_risk) ? [{ rank: i + 1, score: c.replacement_risk }] : []),
  verified: ['numeric full-list sorting', 'band boundaries and filtering', 'search and combined filters',
    'immutable API rows', 'scroll reset helper', 'detail identity/score/date', 'work-order records', 'unchanged metrics'],
  limitation: 'Pure frontend logic and HTTP QA; does not simulate browser layout, focus, events, or console.',
}, null, 2));
