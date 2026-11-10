import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError, api, type AgentRequest, type AgentResponse } from "../api";

type FormState = {
  destinationQuery: string;
  days: string;
  interests: string;
  budget: string;
  travelers: string;
  originLat: string;
  originLon: string;
  newBudget: string;
};

const initialForm: FormState = {
  destinationQuery: "",
  days: "2",
  interests: "",
  budget: "",
  travelers: "1",
  originLat: "",
  originLon: "",
  newBudget: "",
};

function numberOrNull(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

export default function Agents() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [result, setResult] = useState<AgentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function basePayload(): AgentRequest {
    return {
      destination_query: form.destinationQuery || null,
      days: Number(form.days),
      interests: form.interests
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      budget: numberOrNull(form.budget),
      travelers: Number(form.travelers),
      origin_latitude: numberOrNull(form.originLat),
      origin_longitude: numberOrNull(form.originLon),
    };
  }

  async function run(kind: "itinerary" | "rain" | "budget") {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload = basePayload();
      if (kind === "itinerary") {
        setResult(await api.itinerary(payload));
      } else {
        setResult(
          await api.adjust({
            ...payload,
            change: kind,
            new_budget: kind === "budget" ? numberOrNull(form.newBudget) : null,
          }),
        );
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo ejecutar el agente");
    } finally {
      setLoading(false);
    }
  }

  function submitItinerary(event: FormEvent) {
    event.preventDefault();
    void run("itinerary");
  }

  return (
    <section>
      {error && <p className="error">{error}</p>}

      <div className="grid">
        <div className="card">
          <h2>Planificador de itinerarios</h2>
          <form onSubmit={submitItinerary}>
            <label>
              Destino o preferencia
              <input
                value={form.destinationQuery}
                onChange={(event) =>
                  setForm({ ...form, destinationQuery: event.target.value })
                }
                placeholder="Antigua Guatemala, playa, cultura…"
              />
            </label>
            <label>
              Intereses (separados por coma)
              <input
                value={form.interests}
                onChange={(event) =>
                  setForm({ ...form, interests: event.target.value })
                }
                placeholder="cultura, naturaleza"
              />
            </label>
            <label>
              Días
              <input
                type="number"
                min="1"
                max="7"
                value={form.days}
                onChange={(event) => setForm({ ...form, days: event.target.value })}
              />
            </label>
            <label>
              Presupuesto (USD)
              <input
                type="number"
                min="0"
                value={form.budget}
                onChange={(event) => setForm({ ...form, budget: event.target.value })}
              />
            </label>
            <label>
              Viajeros
              <input
                type="number"
                min="1"
                max="20"
                value={form.travelers}
                onChange={(event) =>
                  setForm({ ...form, travelers: event.target.value })
                }
              />
            </label>
            <div className="grid">
              <label>
                Latitud de origen
                <input
                  type="number"
                  step="0.0001"
                  value={form.originLat}
                  onChange={(event) =>
                    setForm({ ...form, originLat: event.target.value })
                  }
                />
              </label>
              <label>
                Longitud de origen
                <input
                  type="number"
                  step="0.0001"
                  value={form.originLon}
                  onChange={(event) =>
                    setForm({ ...form, originLon: event.target.value })
                  }
                />
              </label>
            </div>
            <button type="submit" disabled={loading}>
              {loading ? "Planificando…" : "Generar itinerario"}
            </button>
          </form>
        </div>

        <div className="card">
          <h2>Ajustar un plan</h2>
          <p className="hint">
            Recalcula el itinerario ante lluvia o un nuevo presupuesto.
          </p>
          <label>
            Nuevo presupuesto (USD)
            <input
              type="number"
              min="0"
              value={form.newBudget}
              onChange={(event) =>
                setForm({ ...form, newBudget: event.target.value })
              }
            />
          </label>
          <div className="button-row">
            <button type="button" disabled={loading} onClick={() => void run("rain")}>
              Ajustar por lluvia
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => void run("budget")}
            >
              Ajustar por presupuesto
            </button>
          </div>
        </div>
      </div>

      {result && (
        <div className="card">
          <h2>{result.service_slug}</h2>
          <p>{result.summary}</p>

          {result.missing_info.length > 0 && (
            <p className="warning">
              Falta información: {result.missing_info.join(", ")}
            </p>
          )}

          {result.destination && (
            <p>
              <strong>Destino:</strong> {result.destination.name} ·{" "}
              {result.destination.region}, {result.destination.country}
            </p>
          )}

          <div className="stats">
            <div className="card">
              <span>Costo estimado</span>
              <strong>
                {result.currency} {result.estimated_cost}
              </strong>
            </div>
            <div className="card">
              <span>Presupuesto</span>
              <strong>
                {result.budget === null ? "—" : `${result.currency} ${result.budget}`}
              </strong>
            </div>
            <div className="card">
              <span>Distancia</span>
              <strong>
                {result.distance_km === null ? "—" : `${result.distance_km} km`}
              </strong>
            </div>
            <div className="card">
              <span>Clima</span>
              <strong>
                {result.weather.available
                  ? result.weather.cached
                    ? "verificado (caché)"
                    : "verificado"
                  : "no verificado"}
              </strong>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <div className="warning">
              {result.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}

          {result.itinerary.length > 0 && (
            <div>
              <h3>Itinerario</h3>
              {result.itinerary.map((day) => (
                <div key={day.day}>
                  <h4>Día {day.day}</h4>
                  <ul className="list">
                    {day.activities.map((activity) => (
                      <li key={activity.id}>
                        <span>{activity.name}</span>
                        <span className="badge">{activity.category}</span>
                        <span className="badge">
                          {activity.currency} {activity.estimated_cost}
                        </span>
                      </li>
                    ))}
                    {day.activities.length === 0 && <li>Sin actividades.</li>}
                  </ul>
                </div>
              ))}
            </div>
          )}

          {result.replaced.length > 0 && (
            <div>
              <h3>Cambios aplicados</h3>
              <ul className="list">
                {result.replaced.map((change, index) => (
                  <li key={index}>
                    <span>
                      {String(change.removed)} →{" "}
                      {change.added ? String(change.added) : "sin reemplazo"}
                    </span>
                    <span className="badge">{String(change.reason)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid">
            <div>
              <h3>Pasos</h3>
              <ul className="list">
                {result.steps.map((step, index) => (
                  <li key={index}>
                    <span>{step.tool}</span>
                    <span className="badge">{step.status}</span>
                    <span className="hint">{step.detail}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Fuentes</h3>
              <ul className="list">
                {result.sources.map((source, index) => (
                  <li key={index}>
                    <span>
                      {String(source.type)}: {String(source.name)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <p className="hint">
            {result.tokens_total} tokens usados · {result.tokens_remaining} restantes
          </p>
        </div>
      )}
    </section>
  );
}
