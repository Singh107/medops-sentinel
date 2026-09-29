// Display-only helpers. Backend scores and bands remain authoritative.
export type RiskStatus = 'LOW RISK' | 'MONITOR' | 'HIGH RISK';
export type RiskSort = 'descending' | 'ascending';

export const statusColors: Record<RiskStatus, string> = {
  'LOW RISK': '#22c55e', MONITOR: '#f59e0b', 'HIGH RISK': '#f87171',
};

export const bandForScore = (value: number): RiskStatus =>
  value >= 70 ? 'HIGH RISK' : value >= 40 ? 'MONITOR' : 'LOW RISK';

type ReviewRow = {
  component_id: string; machine_id: string; part_type: string;
  replacement_risk: number; status: RiskStatus;
};

export function reviewRows<T extends ReviewRow>(rows: readonly T[], search: string, band: RiskStatus | 'ALL', sort: RiskSort): T[] {
  const query = search.trim().toLowerCase();
  return rows.filter(c => (band === 'ALL' || c.status === band) &&
    `${c.part_type} ${c.machine_id} ${c.component_id}`.toLowerCase().includes(query))
    .sort((a, b) => (sort === 'descending' ? b.replacement_risk - a.replacement_risk : a.replacement_risk - b.replacement_risk)
      || a.component_id.localeCompare(b.component_id));
}

export function resetReviewScroll(container: { scrollTop: number } | null) {
  if (container) container.scrollTop = 0;
}
