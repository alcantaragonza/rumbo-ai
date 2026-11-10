"""Smoke test de extremo a extremo contra un entorno de Rumbo AI."""

import argparse
import sys
from typing import Any

import httpx


def check(response: httpx.Response, label: str) -> Any:
    if response.status_code >= 400:
        print(f"FALLO {label}: HTTP {response.status_code} {response.text[:300]}")
        sys.exit(1)
    print(f"OK    {label}: HTTP {response.status_code}")
    if response.status_code == 204:
        return None
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default="admin@rumbo.ai")
    parser.add_argument("--password", default="Admin123!")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=60, follow_redirects=True) as client:
        user = check(
            client.post(
                "/api/v1/auth/login",
                json={"email": args.email, "password": args.password},
            ),
            "login",
        )
        print(f"      usuario: {user['email']} ({user['role']})")

        destinations = check(client.get("/api/v1/destinations"), "catálogo")
        if not destinations:
            print("FALLO catálogo: no hay destinos")
            sys.exit(1)
        print(f"      destinos: {len(destinations)}")

        chat = check(
            client.post(
                "/api/v1/chat",
                json={"message": "Quiero visitar Antigua Guatemala"},
            ),
            "chat",
        )
        print(
            f"      conversación {chat['conversation_id']}, "
            f"{len(chat['sources'])} fuentes, {chat['tokens_total']} tokens"
        )

        itinerary = check(
            client.post(
                "/api/v1/agents/itinerary",
                json={
                    "destination_id": destinations[0]["id"],
                    "days": 1,
                    "travelers": 1,
                },
            ),
            "agente itinerario",
        )
        print(
            f"      {len(itinerary['itinerary'])} día(s), "
            f"costo {itinerary['currency']} {itinerary['estimated_cost']}, "
            f"{len(itinerary['steps'])} pasos"
        )

        history = check(client.get("/api/v1/history/conversations"), "historial")
        if not any(item["id"] == chat["conversation_id"] for item in history):
            print("FALLO historial: no aparece la conversación del chat")
            sys.exit(1)

        report = check(client.get("/api/v1/reports/usage"), "reporte")
        usage = check(client.get("/api/v1/usage"), "consumo")
        if report["totals"]["tokens_total"] != usage["tokens_total"]:
            print("FALLO reporte: los totales no coinciden con /usage")
            sys.exit(1)
        print(
            f"      consultas: {report['totals']['requests']}, "
            f"tokens: {report['totals']['tokens_total']}"
        )

        check(client.post("/api/v1/auth/logout"), "logout")
        print("SMOKE TEST COMPLETADO")


if __name__ == "__main__":
    main()
