import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  api,
  type Service,
  type UsageReportResponse,
  type User,
} from "../api";

type Props = {
  isAdmin: boolean;
};

export default function Reports({ isAdmin }: Props) {
  const [report, setReport] = useState<UsageReportResponse | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [users, setUsers] = useState<User[]>([]);
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
      setReport(await api.reportUsage(buildParams()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar el reporte");
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

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    void load();
  }

  const byService = report
    ? Array.from(
        report.rows.reduce((accumulator, row) => {
          const current = accumulator.get(row.service_name) ?? {
            requests: 0,
            tokens: 0,
          };
          accumulator.set(row.service_name, {
            requests: current.requests + row.requests,
            tokens: current.tokens + row.tokens_total,
          });
          return accumulator;
        }, new Map<string, { requests: number; tokens: number }>()),
      )
    : [];
  const maxTokens = Math.max(1, ...byService.map(([, value]) => value.tokens));

  return (
    <section>
      {error && <p className="error">{error}</p>}

      <form className="card filters" onSubmit={applyFilters}>
        {isAdmin && (
          <label>
            Usuario
            <select
              value={filters.userId}
              onChange={(event) =>
                setFilters({ ...filters, userId: event.target.value })
              }
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
            onChange={(event) =>
              setFilters({ ...filters, dateTo: event.target.value })
            }
          />
        </label>
        <button type="submit">Filtrar</button>
      </form>

      {report && (
        <>
          <div className="stats">
            <div className="card">
              <span>Consultas</span>
              <strong>{report.totals.requests}</strong>
            </div>
            <div className="card">
              <span>Bloqueadas</span>
              <strong>{report.totals.blocked}</strong>
            </div>
            <div className="card">
              <span>Tokens entrada</span>
              <strong>{report.totals.tokens_in}</strong>
            </div>
            <div className="card">
              <span>Tokens salida</span>
              <strong>{report.totals.tokens_out}</strong>
            </div>
            <div className="card">
              <span>Tokens totales</span>
              <strong>{report.totals.tokens_total}</strong>
            </div>
          </div>
          <p className="hint">
            Zona horaria {report.timezone} · moneda {report.currency} · generado{" "}
            {new Date(report.generated_at).toLocaleString("es-GT")}
          </p>

          <div className="card">
            <h2>Consumo por servicio</h2>
            {byService.map(([name, value]) => (
              <div key={name} className="bar-row">
                <span className="bar-label">{name}</span>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${(value.tokens / maxTokens) * 100}%` }}
                  />
                </div>
                <span className="bar-value">
                  {value.requests} consultas · {value.tokens} tokens
                </span>
              </div>
            ))}
            {byService.length === 0 && <p>Sin datos para los filtros.</p>}
          </div>

          <div className="card">
            <h2>Detalle diario</h2>
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Servicio</th>
                  <th>Usuario</th>
                  <th>Consultas</th>
                  <th>Bloqueadas</th>
                  <th>Entrada</th>
                  <th>Salida</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {report.rows.map((row) => (
                  <tr key={`${row.date}-${row.service_id}-${row.user_id}`}>
                    <td>{row.date}</td>
                    <td>{row.service_name}</td>
                    <td>{row.user_email}</td>
                    <td>{row.requests}</td>
                    <td>{row.blocked}</td>
                    <td>{row.tokens_in}</td>
                    <td>{row.tokens_out}</td>
                    <td>{row.tokens_total}</td>
                  </tr>
                ))}
                {report.rows.length === 0 && (
                  <tr>
                    <td colSpan={8}>Sin datos para los filtros.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
