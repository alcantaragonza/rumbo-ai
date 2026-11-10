import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  api,
  type Activity,
  type Destination,
  type DestinationInput,
} from "../api";

const emptyDestination: DestinationInput = {
  name: "",
  description: "",
  region: "",
  country: "Guatemala",
  latitude: null,
  longitude: null,
  interests: [],
  season: null,
};

const emptyActivity = {
  name: "",
  description: "",
  category: "",
  estimated_cost: "0",
  duration_minutes: "60",
};

export default function CatalogAdmin() {
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [destinationForm, setDestinationForm] =
    useState<DestinationInput>(emptyDestination);
  const [interestsText, setInterestsText] = useState("");
  const [activityForm, setActivityForm] = useState(emptyActivity);
  const [error, setError] = useState<string | null>(null);

  async function loadDestinations() {
    try {
      setDestinations(await api.destinations(true));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar el catálogo");
    }
  }

  async function loadActivities(destinationId: number) {
    try {
      setActivities(await api.activities(destinationId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudieron cargar las actividades");
    }
  }

  useEffect(() => {
    void loadDestinations();
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setActivities([]);
      return;
    }
    void loadActivities(selectedId);
  }, [selectedId]);

  async function createDestination(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const created = await api.createDestination({
        ...destinationForm,
        interests: interestsText
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setDestinationForm(emptyDestination);
      setInterestsText("");
      await loadDestinations();
      setSelectedId(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el destino");
    }
  }

  async function editDestination(destination: Destination) {
    const name = window.prompt("Nuevo nombre del destino", destination.name);
    if (!name || name === destination.name) {
      return;
    }
    try {
      await api.updateDestination(destination.id, { name });
      await loadDestinations();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar el destino");
    }
  }

  async function deactivateDestination(destination: Destination) {
    if (!window.confirm(`¿Desactivar ${destination.name}?`)) {
      return;
    }
    try {
      await api.deleteDestination(destination.id);
      if (selectedId === destination.id) {
        setSelectedId(null);
      }
      await loadDestinations();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo desactivar el destino");
    }
  }

  async function createActivity(event: FormEvent) {
    event.preventDefault();
    if (selectedId === null) {
      return;
    }
    setError(null);
    try {
      await api.createActivity({
        destination_id: selectedId,
        name: activityForm.name,
        description: activityForm.description,
        category: activityForm.category,
        estimated_cost: Number(activityForm.estimated_cost),
        duration_minutes: Number(activityForm.duration_minutes),
      });
      setActivityForm(emptyActivity);
      await loadActivities(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear la actividad");
    }
  }

  async function deactivateActivity(activity: Activity) {
    if (!window.confirm(`¿Desactivar ${activity.name}?`)) {
      return;
    }
    try {
      await api.deleteActivity(activity.id);
      if (selectedId !== null) {
        await loadActivities(selectedId);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo desactivar la actividad");
    }
  }

  return (
    <section>
      {error && <p className="error">{error}</p>}

      <div className="grid">
        <div className="card">
          <h2>Nuevo destino</h2>
          <form onSubmit={createDestination}>
            <label>
              Nombre
              <input
                value={destinationForm.name}
                onChange={(event) =>
                  setDestinationForm({ ...destinationForm, name: event.target.value })
                }
                required
              />
            </label>
            <label>
              Descripción
              <textarea
                value={destinationForm.description}
                onChange={(event) =>
                  setDestinationForm({
                    ...destinationForm,
                    description: event.target.value,
                  })
                }
                required
              />
            </label>
            <label>
              Región
              <input
                value={destinationForm.region}
                onChange={(event) =>
                  setDestinationForm({ ...destinationForm, region: event.target.value })
                }
                required
              />
            </label>
            <label>
              País
              <input
                value={destinationForm.country}
                onChange={(event) =>
                  setDestinationForm({ ...destinationForm, country: event.target.value })
                }
                required
              />
            </label>
            <label>
              Intereses (separados por coma)
              <input
                value={interestsText}
                onChange={(event) => setInterestsText(event.target.value)}
                placeholder="cultura, naturaleza"
              />
            </label>
            <label>
              Temporada
              <input
                value={destinationForm.season ?? ""}
                onChange={(event) =>
                  setDestinationForm({
                    ...destinationForm,
                    season: event.target.value || null,
                  })
                }
              />
            </label>
            <button type="submit">Crear destino</button>
          </form>
        </div>

        <div className="card">
          <h2>Destinos</h2>
          <ul className="list">
            {destinations.map((destination) => (
              <li key={destination.id} className={destination.is_active ? "" : "inactive"}>
                <button className="link" onClick={() => setSelectedId(destination.id)}>
                  {destination.name}
                </button>
                <span className="badge">{destination.is_active ? "activo" : "inactivo"}</span>
                <button onClick={() => void editDestination(destination)}>Editar</button>
                <button
                  className="danger"
                  onClick={() => void deactivateDestination(destination)}
                  disabled={!destination.is_active}
                >
                  Desactivar
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {selectedId !== null && (
        <div className="grid">
          <div className="card">
            <h2>Nueva actividad</h2>
            <form onSubmit={createActivity}>
              <label>
                Nombre
                <input
                  value={activityForm.name}
                  onChange={(event) =>
                    setActivityForm({ ...activityForm, name: event.target.value })
                  }
                  required
                />
              </label>
              <label>
                Descripción
                <textarea
                  value={activityForm.description}
                  onChange={(event) =>
                    setActivityForm({ ...activityForm, description: event.target.value })
                  }
                  required
                />
              </label>
              <label>
                Categoría
                <input
                  value={activityForm.category}
                  onChange={(event) =>
                    setActivityForm({ ...activityForm, category: event.target.value })
                  }
                  required
                />
              </label>
              <label>
                Costo estimado (USD)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={activityForm.estimated_cost}
                  onChange={(event) =>
                    setActivityForm({
                      ...activityForm,
                      estimated_cost: event.target.value,
                    })
                  }
                />
              </label>
              <label>
                Duración (minutos)
                <input
                  type="number"
                  min="1"
                  value={activityForm.duration_minutes}
                  onChange={(event) =>
                    setActivityForm({
                      ...activityForm,
                      duration_minutes: event.target.value,
                    })
                  }
                />
              </label>
              <button type="submit">Crear actividad</button>
            </form>
          </div>

          <div className="card">
            <h2>Actividades del destino</h2>
            <ul className="list">
              {activities.map((activity) => (
                <li key={activity.id}>
                  <span>{activity.name}</span>
                  <span className="badge">USD {activity.estimated_cost}</span>
                  <button
                    className="danger"
                    onClick={() => void deactivateActivity(activity)}
                  >
                    Desactivar
                  </button>
                </li>
              ))}
              {activities.length === 0 && <li>Sin actividades activas.</li>}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
