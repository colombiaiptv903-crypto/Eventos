#!/usr/bin/env python3
"""
Generador de agenda deportiva diaria para CineStream.
Fuente: ESPN API (gratuita, sin clave) + eventos manuales en eventos_extra.json
Salida: agenda123.json (formato compatible con la app CineStream)

Ejecución: python generate_agenda.py
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ── Zona horaria Colombia (UTC-5, sin horario de verano) ──────────────────────
TZ_COL = timezone(timedelta(hours=-5))

# ── Ligas de ESPN con su slug, nombre legible y canales por defecto ───────────
LIGAS = [
    {
        "slug": "col.1",
        "nombre": "Liga BetPlay",
        "categoria": "Fútbol",
        "canales_default": ["Win Sports", "Win Sports+"],
    },
    {
        "slug": "col.2",
        "nombre": "Primera B",
        "categoria": "Fútbol",
        "canales_default": ["Win Sports"],
    },
    {
        "slug": "conmebol.libertadores",
        "nombre": "Copa Libertadores",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 2", "DirecTV Sports"],
    },
    {
        "slug": "conmebol.sudamericana",
        "nombre": "Copa Sudamericana",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 3", "DirecTV Sports 2"],
    },
    {
        "slug": "conmebol.recopa",
        "nombre": "Recopa Sudamericana",
        "categoria": "Fútbol",
        "canales_default": ["ESPN", "DirecTV Sports"],
    },
    {
        "slug": "uefa.champions",
        "nombre": "Champions League",
        "categoria": "Fútbol",
        "canales_default": ["ESPN", "ESPN 2"],
    },
    {
        "slug": "uefa.europa",
        "nombre": "Europa League",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 3", "ESPN 4"],
    },
    {
        "slug": "eng.1",
        "nombre": "Premier League",
        "categoria": "Fútbol",
        "canales_default": ["ESPN", "ESPN 3"],
    },
    {
        "slug": "esp.1",
        "nombre": "La Liga",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 2", "DirecTV Sports"],
    },
    {
        "slug": "ger.1",
        "nombre": "Bundesliga",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 4", "ESPN 5"],
    },
    {
        "slug": "ita.1",
        "nombre": "Serie A",
        "categoria": "Fútbol",
        "canales_default": ["ESPN", "ESPN 2"],
    },
    {
        "slug": "fra.1",
        "nombre": "Ligue 1",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 3"],
    },
    {
        "slug": "mex.1",
        "nombre": "Liga MX",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 2", "TUDN"],
    },
    {
        "slug": "arg.1",
        "nombre": "Liga Argentina",
        "categoria": "Fútbol",
        "canales_default": ["TyC Sports", "ESPN"],
    },
    {
        "slug": "bra.1",
        "nombre": "Brasileirão",
        "categoria": "Fútbol",
        "canales_default": ["Sport TV", "ESPN"],
    },
    {
        "slug": "usa.1",
        "nombre": "MLS",
        "categoria": "Fútbol",
        "canales_default": ["ESPN 2"],
    },
    {
        "slug": "fifa.worldq.conmebol",
        "nombre": "Eliminatorias CONMEBOL",
        "categoria": "Fútbol",
        "canales_default": ["RCN", "Caracol", "ESPN"],
    },
    {
        "slug": "fifa.world",
        "nombre": "Copa del Mundo",
        "categoria": "Fútbol",
        "canales_default": ["RCN", "Caracol", "ESPN"],
    },
]


def cargar_json(ruta: str):
    """Lee un archivo JSON local."""
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [WARN] No se pudo leer {ruta}: {e}")
        return {}


def fetch_json(url: str):
    """Descarga JSON desde una URL."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10; K) "
                "AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] Error al descargar {url}: {e}")
        return None


def utc_to_colombia(utc_str: str) -> tuple[str, str]:
    """
    Convierte ISO date string UTC a fecha y hora colombiana.
    Retorna (fecha_str, hora_str) → ("2026-04-17", "16:00")
    """
    try:
        # ESPN usa formato: "2026-04-17T21:00Z"
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        col_dt = utc_dt.astimezone(TZ_COL)
        fecha = col_dt.strftime("%Y-%m-%d")
        hora = col_dt.strftime("%H:%M")
        return fecha, hora
    except Exception:
        return "", ""


def obtener_eventos_espn(canales_map: dict, hoy: str) -> list:
    """
    Descarga eventos de hoy desde múltiples ligas de ESPN.
    Retorna lista de eventos en el formato nuevo de CineStream.
    """
    eventos = []

    for liga in LIGAS:
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{liga['slug']}/scoreboard"
        )
        print(f"  Consultando {liga['nombre']} ({liga['slug']})...")
        data = fetch_json(url)
        if not data:
            continue

        for event in data.get("events", []):
            # Fecha y hora en Colombia
            fecha_utc = event.get("date", "")
            fecha, hora = utc_to_colombia(fecha_utc)

            # Solo eventos de hoy
            if fecha != hoy:
                continue

            # Equipos
            competitions = event.get("competitions", [{}])
            comp = competitions[0] if competitions else {}
            teams = comp.get("competitors", [])
            home = next((t for t in teams if t.get("homeAway") == "home"), {})
            away = next((t for t in teams if t.get("homeAway") == "away"), {})
            home_name = home.get("team", {}).get("displayName", "?")
            away_name = away.get("team", {}).get("displayName", "?")

            titulo = f"{liga['nombre']}: {home_name} vs {away_name}"

            # Estado
            status_type = event.get("status", {}).get("type", {})
            estado = status_type.get("description", "Programado")
            status_str = "En vivo" if status_type.get("state") == "in" else "Pronto"

            # Construir canales
            canales_evento = []
            for nombre_canal in liga["canales_default"]:
                url_canal = canales_map.get(nombre_canal, "")
                if url_canal:
                    canales_evento.append({
                        "nombre": nombre_canal,
                        "iframe": url_canal,
                    })

            if not canales_evento:
                # Sin canal conocido — omitir
                continue

            eventos.append({
                "titulo": titulo,
                "hora": hora,
                "fecha": fecha,
                "categoria": liga["categoria"],
                "canales": canales_evento,
            })

    return eventos


def cargar_eventos_extra(hoy: str) -> list:
    """
    Lee eventos_extra.json y filtra los de hoy (o sin fecha).
    Ignora entradas con claves que empiecen por '_' (comentarios).
    """
    raw = cargar_json("eventos_extra.json")
    if not isinstance(raw, list):
        return []

    resultado = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        # Saltar entradas de comentario
        if any(k.startswith("_") for k in item.keys()):
            continue
        fecha = item.get("fecha", "")
        # Incluir si es de hoy o sin fecha (en vivo)
        if fecha and fecha != hoy:
            continue
        resultado.append(item)
    return resultado


def main():
    # Fecha de hoy en Colombia
    hoy_col = datetime.now(TZ_COL).strftime("%Y-%m-%d")
    print(f"\n=== Generando agenda para {hoy_col} (hora Colombia) ===\n")

    # Cargar mapa de canales
    canales_map = cargar_json("canales.json")
    if not canales_map:
        print("[ERROR] canales.json vacío o no encontrado. Abortando.")
        return

    print(f"Canales disponibles: {len(canales_map)}")

    # Obtener eventos automáticos desde ESPN
    print("\n--- ESPN API ---")
    eventos_espn = obtener_eventos_espn(canales_map, hoy_col)
    print(f"Eventos ESPN encontrados para hoy: {len(eventos_espn)}")

    # Cargar eventos manuales / extras
    print("\n--- Eventos extras/manuales ---")
    eventos_manual = cargar_eventos_extra(hoy_col)
    print(f"Eventos manuales: {len(eventos_manual)}")

    # Combinar: primero manuales (tienen prioridad) luego ESPN
    todos = eventos_manual + eventos_espn

    # Ordenar por hora
    def sort_key(e):
        hora = e.get("hora", "99:99")
        return hora

    todos.sort(key=sort_key)

    print(f"\nTotal eventos en agenda: {len(todos)}")

    # Guardar agenda123.json
    with open("agenda123.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

    print(f"\nOK: agenda123.json generado con {len(todos)} eventos para {hoy_col}")

    # Mostrar resumen
    for ev in todos:
        canales_str = ", ".join(c["nombre"] for c in ev.get("canales", []))
        print(f"  {ev.get('hora','?')} | {ev.get('titulo','?')} - {canales_str}")


if __name__ == "__main__":
    main()
