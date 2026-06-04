export type EventCategory =
  | "devis"
  | "support"
  | "facturation"
  | "rendez_vous"
  | "relances"
  | "autre";

export interface DashboardMetrics {
  period_start: string;
  period_end: string;
  hours_lost_estimate: number;
  repetitive_tasks_count: number;
  automation_potential_score: number;
  category_breakdown: Record<string, number>;
  insights: { label: string; value: string; detail?: string }[];
}

export interface Suggestion {
  id: string;
  title: string;
  description: string;
  monthly_frequency: number;
  estimated_hours_saved: number;
  workflow_draft: Record<string, unknown> | null;
  status: string;
  roi_score: number;
  risk_notes: string | null;
}
