import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError, api, type ChatSource } from "../api";

type Turn = {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  insufficient?: boolean;
  tokens?: number;
};

export default function Chat() {
  const [messages, setMessages] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || loading) {
      return;
    }
    setInput("");
    setError(null);
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: text }]);

    try {
      const response = await api.chat(text, conversationId);
      setConversationId(response.conversation_id);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.message,
          sources: response.sources,
          insufficient: response.insufficient_context,
          tokens: response.tokens_total,
        },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "No se pudo obtener respuesta";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function newConversation() {
    setMessages([]);
    setConversationId(null);
    setError(null);
  }

  return (
    <section>
      <div className="card">
        <div className="chat-header">
          <h2>Chat con RAG</h2>
          <button onClick={newConversation}>Nueva conversación</button>
        </div>
        {error && <p className="error">{error}</p>}

        <div className="chat-window">
          {messages.length === 0 && (
            <p className="hint">
              Pregunta por destinos, actividades o pide un itinerario. Las
              respuestas citan las fuentes del catálogo.
            </p>
          )}
          {messages.map((turn, index) => (
            <div key={index} className={`chat-turn ${turn.role}`}>
              <strong>{turn.role === "user" ? "Tú" : "Rumbo AI"}</strong>
              <p>{turn.content}</p>
              {turn.insufficient && (
                <p className="warning">
                  No hay información suficiente en el catálogo para esta
                  pregunta.
                </p>
              )}
              {turn.sources && turn.sources.length > 0 && (
                <ul className="sources">
                  {turn.sources.map((source) => (
                    <li key={`${source.type}-${source.id}`}>
                      {source.type === "activity" ? "Actividad" : "Destino"}:{" "}
                      {source.name}
                      {source.destination_name &&
                        source.destination_name !== source.name &&
                        ` (${source.destination_name})`}
                    </li>
                  ))}
                </ul>
              )}
              {typeof turn.tokens === "number" && (
                <span className="badge">{turn.tokens} tokens</span>
              )}
            </div>
          ))}
          {loading && <p className="hint">Pensando…</p>}
        </div>

        <form className="chat-form" onSubmit={send}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Escribe tu pregunta…"
            aria-label="Mensaje"
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Enviar
          </button>
        </form>
      </div>
    </section>
  );
}
