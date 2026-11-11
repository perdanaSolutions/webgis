export type MonitoringStatus = "online" | "offline";

export type MonitoringQuery = {
  search?: string;
  status?: MonitoringStatus | "";
  page?: number;
  limit?: number;
};

/** Query string GET /v1/monitoring/users; parameter kosong tidak dikirim. */
export function buildMonitoringQuery(query: MonitoringQuery = {}) {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (typeof query.page === "number") params.set("page", String(query.page));
  if (typeof query.limit === "number") params.set("limit", String(query.limit));
  return params.toString();
}
