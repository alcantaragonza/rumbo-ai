import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  api,
  type ConversationDetail,
  type ConversationSummary,
  type Service,
  type UsageSummary,
  type User,
} from "../api";

type Props = {
  isAdmin: boolean;
};

function formatDate(value: string) {
  return new Date(value).toLocaleString("es-GT");
}

export default function History({ isAdmin }: Props) {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    userId: "",
    serviceId: "",
    dateFrom: "",
    dateTo: "",
  });

  function buildParams() {
    return {
      user_id: isAdmin && filters.userId ? Number(filters.userId) : undefined,
      service_id: filters.serviceId ? Number(filters.serviceId) : undefined,
      date_from: filters.dateFrom ? `${filters.dateFrom}T00:00:00Z` : undefined,
      date_to: filters.dateTo ? `${filters.dateTo}T23:59:59Z` : undefined,
    };
  }

  async function load() {
    setError(null);
    try {
      const params = buildParams();
      const [usageData, conversationData] = await Promise.all([
        api.usage(params),
        api.conversations(params),
      ]);
      setUsage(usageData);
      setConversations(conversationData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar el historial");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    api.services().then(setServices).catch(() => setServices([]));
    if (isAdmin) {
      api.users().then(setUsers).catch(() => setUsers([]));
    }
  }, [isAdmin]);

  async function openConversation(id: number) {
    try {
      setSelected(await api.conversation(id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo abrir la conversación");
    }
  }

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    void load();
  }

  return (
    <section>
      {error && <p className="error">{error}</p>}

      <form className="card filters" onSubmit={applyFilters}>
        {isAdmin && (
          <label>
            Usuario
            <select
              value={filters.userId}
              onChange={(event) => setFilters({ ...filters, userId: event.target.value })}
            >
              <option value="">Todos</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.email}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Servicio
          <select
            value={filters.serviceId}
            onChange={(event) =>
              setFilters({ ...filters, serviceId: event.target.value })
            }
          >
            <option value="">Todos</option>
            {services.map((service) => (
              <option key={service.id} value={service.id}>
                {service.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Desde
          <input
            type="date"
            value={filters.dateFrom}
            onChange={(event) =>
              setFilters({ ...filters, dateFrom: event.target.value })
            }
          />
        </label>
        <label>
          Hasta
          <input
            type="date"
            value={filters.dateTo}
            onChange={(event) => setFilters({ ...filters, dateTo: event.target.value })}
          />
        </label>
        <button type="submit">Filtrar</button>
      </form>

      {usage && (
        <div className="stats">
          <div className="card">
            <span>Consultas</span>
            <strong>{usage.requests}</strong>
          </div>
          <div className="card">
            <span>Tokens usados</span>
            <strong>{usage.tokens_used}</strong>
          </div>
          <div className="card">
            <span>Tokens restantes</span>
            <strong>{usage.tokens_remaining ?? "—"}</strong>
          </div>
          <div className="card">
            <span>Bloqueadas</span>
            <strong>{usage.blocked}</strong>
          </div>
        </div>
      )}

      {usage && usage.by_service.length > 0 && (
        <div className="card">
          <h2>Consumo por servicio</h2>
          <table>
            <thead>
              <tr>
                <th>Servicio</th>
                <th>Consultas</th>
                <th>Bloqueadas</th>
                <th>Tokens entrada</th>
                <th>Tokens salida</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {usage.by_service.map((row) => (
                <tr key={row.service_id}>
                  <td>{row.service_name}</td>
                  <td>{row.requests}</td>
                  <td>{row.blocked}</td>
                  <td>{row.tokens_in}</td>
                  <td>{row.tokens_out}</td>
                  <td>{row.tokens_total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid">
        <div className="card">
          <h2>Conversaciones</h2>
          <ul className="list">
            {conversations.map((conversation) => (
              <li key={conversation.id}>
                <button
                  className="link"
                  onClick={() => void openConversation(conversation.id)}
                >
                  {conversation.title}
                </button>
                <span className="badge">{conversation.service_name}</span>
                <span className="badge">{conversation.tokens_total} tokens</span>
                <span className="badge">{formatDate(conversation.created_at)}</span>
              </li>
            ))}
            {conversations.length === 0 && <li>Sin conversaciones para los filtros.</li>}
          </ul>
        </div>

        <div className="card">
          <h2>Detalle</h2>
          {selected ? (
            <>
              <p className="hint">
                {selected.title} · {selected.service_name} · {selected.tokens_total} tokens
              </p>
              {selected.messages.map((message) => (
                <div key={message.id} className="message">
                  <strong>{message.role}</strong>
                  <p>{message.content}</p>
                  <span className="badge">
                    {message.tokens_in + message.tokens_out} tokens
                  </span>
                </div>
              ))}
            </>
          ) : (
            <p>Selecciona una conversación para ver sus mensajes.</p>
          )}
        </div>
      </div>
    </section>
  );
}
