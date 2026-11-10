export type Role = "admin" | "user";

export type User = {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  token_limit: number;
};

export type Activity = {
  id: number;
  destination_id: number;
  name: string;
  description: string;
  category: string;
  estimated_cost: number;
  currency: string;
  duration_minutes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Destination = {
  id: number;
  name: string;
  description: string;
  region: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  interests: string[];
  season: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  activities: Activity[];
};

export type DestinationInput = {
  name: string;
  description: string;
  region: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  interests: string[];
  season: string | null;
  is_active?: boolean;
};

export type ActivityInput = {
  destination_id: number;
  name: string;
  description: string;
  category: string;
  estimated_cost: number;
  currency?: string;
  duration_minutes: number;
  is_active?: boolean;
};

export type Service = {
  id: number;
  slug: string;
  name: string;
  kind: string;
  is_enabled: boolean;
  model: string;
};

export type ServiceUsage = {
  service_id: number;
  service_slug: string;
  service_name: string;
  requests: number;
  blocked: number;
  tokens_in: number;
  tokens_out: number;
  tokens_total: number;
};

export type UsageSummary = {
  user_id: number | null;
  token_limit: number | null;
  tokens_used: number;
  tokens_remaining: number | null;
  requests: number;
  blocked: number;
  tokens_in: number;
  tokens_out: number;
  tokens_total: number;
  by_service: ServiceUsage[];
};

export type ConversationSummary = {
  id: number;
  title: string;
  service_id: number;
  service_slug: string;
  service_name: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  tokens_total: number;
};

export type ConversationMessage = {
  id: number;
  role: string;
  content: string;
  sources: Record<string, unknown>[];
  tokens_in: number;
  tokens_out: number;
  created_at: string;
};

export type ConversationDetail = Omit<ConversationSummary, "message_count"> & {
  messages: ConversationMessage[];
};

export type ChatSource = {
  type: string;
  id: number;
  name: string;
  destination_id: number | null;
  destination_name: string | null;
};

export type ChatResponse = {
  conversation_id: number;
  message: string;
  sources: ChatSource[];
  tokens_in: number;
  tokens_out: number;
  tokens_total: number;
  tokens_remaining: number;
  insufficient_context: boolean;
};

export type AgentActivity = {
  id: number;
  name: string;
  description: string;
  category: string;
  estimated_cost: number;
  currency: string;
  duration_minutes: number;
};

export type AgentDay = {
  day: number;
  activities: AgentActivity[];
};

export type AgentWeather = {
  available?: boolean;
  cached?: boolean;
  reason?: string;
  error?: string;
  daily?: Record<string, unknown>;
};

export type AgentDestination = {
  id: number;
  name: string;
  description: string;
  region: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
};

export type AgentResponse = {
  service_slug: string;
  summary: string;
  destination: AgentDestination | null;
  days: number;
  itinerary: AgentDay[];
  weather: AgentWeather;
  distance_km: number | null;
  estimated_cost: number;
  currency: string;
  budget: number | null;
  within_budget: boolean | null;
  steps: Array<{ tool: string; status: string; detail: string }>;
  sources: Array<Record<string, unknown>>;
  warnings: string[];
  missing_info: string[];
  replaced: Array<Record<string, unknown>>;
  tokens_total: number;
  tokens_remaining: number;
};

export type AgentRequest = {
  destination_id?: number | null;
  destination_query?: string | null;
  days: number;
  interests: string[];
  budget?: number | null;
  travelers: number;
  origin_latitude?: number | null;
  origin_longitude?: number | null;
};

export type AdjustAgentRequest = AgentRequest & {
  change: "rain" | "budget";
  new_budget?: number | null;
};

export type UsageReportRow = {
  date: string;
  service_id: number;
  service_slug: string;
  service_name: string;
  user_id: number;
  user_email: string;
  requests: number;
  blocked: number;
  tokens_in: number;
  tokens_out: number;
  tokens_total: number;
};

export type UsageReportTotals = {
  requests: number;
  blocked: number;
  tokens_in: number;
  tokens_out: number;
  tokens_total: number;
};

export type UsageReportResponse = {
  timezone: string;
  currency: string;
  generated_at: string;
  rows: UsageReportRow[];
  totals: UsageReportTotals;
};

export type HistoryParams = {
  user_id?: number;
  service_id?: number;
  date_from?: string;
  date_to?: string;
};

function toQuery(params: HistoryParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `Error ${response.status}`;
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) {
        message = data.detail;
      }
    } catch {
      // El cuerpo no era JSON; se conserva el mensaje genérico.
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),
  destinations: (includeInactive = false) =>
    request<Destination[]>(`/destinations?include_inactive=${includeInactive}`),
  createDestination: (data: DestinationInput) =>
    request<Destination>("/destinations", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateDestination: (id: number, data: Partial<DestinationInput>) =>
    request<Destination>(`/destinations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteDestination: (id: number) =>
    request<void>(`/destinations/${id}`, { method: "DELETE" }),
  activities: (destinationId: number) =>
    request<Activity[]>(`/activities?destination_id=${destinationId}`),
  createActivity: (data: ActivityInput) =>
    request<Activity>("/activities", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateActivity: (id: number, data: Partial<ActivityInput>) =>
    request<Activity>(`/activities/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteActivity: (id: number) =>
    request<void>(`/activities/${id}`, { method: "DELETE" }),
  users: () => request<User[]>("/users"),
  services: () => request<Service[]>("/services"),
  usage: (params: HistoryParams = {}) =>
    request<UsageSummary>(`/usage${toQuery(params)}`),
  conversations: (params: HistoryParams = {}) =>
    request<ConversationSummary[]>(`/history/conversations${toQuery(params)}`),
  conversation: (id: number) =>
    request<ConversationDetail>(`/history/conversations/${id}`),
  chat: (message: string, conversationId?: number | null) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId ?? null,
      }),
    }),
  itinerary: (payload: AgentRequest) =>
    request<AgentResponse>("/agents/itinerary", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  adjust: (payload: AdjustAgentRequest) =>
    request<AgentResponse>("/agents/adjust", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reportUsage: (params: HistoryParams = {}) =>
    request<UsageReportResponse>(`/reports/usage${toQuery(params)}`),
};
