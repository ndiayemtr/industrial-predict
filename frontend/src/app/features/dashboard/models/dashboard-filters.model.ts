export interface DashboardFilters {
  company_id: number;
  /** ISO 8601 with timezone, preferably UTC Z. Inclusive lower bound. */
  start_time: string;
  /** ISO 8601 with timezone. Exclusive upper bound; never adjusted by the service. */
  end_time: string;
  site_id?: number | null;
  equipment_id?: number | null;
}
