#!/usr/bin/env python3
"""
Generador de agenda deportiva diaria para CineStream.

Fuentes:
  - Partidos del dia: ESPN API (gratuita, sin clave de acceso)
  - URLs de canales:  cinestream.json (tu propio repo, siempre actualizado)
  - Eventos extra:    eventos_extra.json (manual, opcional)

Salida: agenda123.json compatible con la app CineStream

Ejecucion: python generate_agenda.py
"""

import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone, timedelta

# ── Configuracion ─────────────────────────────────────────────────────────────

# JSON principal de canales (tu propio repo — lo mantienes actualizado)
CINESTREAM_JSON_URL = (
    "https://raw.githubusercontent.com/colombiaiptv903-crypto/"
    "cinestream/refs/heads/main/cinestream.json"
)

# Zona horaria Colombia (UTC-5, sin horario de verano)
TZ_COL = timezone(timedelta(hours=-5))

# ── Ligas de ESPN: slug, nombre y canales por defecto para Colombia ───────────
LIGAS = [
    {
        "slug": "col.1",
        "nombre": "Liga BetPlay",
        "categoria": "Futbol",
        "canales_default": ["Win Sports", "Win Sports+"],
    },
    {
        "slug": "col.2",
        "nombre": "Primera B Colombia",
        "categoria": "Futbol",
        "canales_default": ["Win Sports"],
    },
    {
        "slug": "conmebol.libertadores",
        "nombre": "Copa Libertadores",
        "categoria": "Futbol",
        "canales_default": ["ESPN 2", "DirecTV Sports"],
    },
    {
        "slug": "conmebol.sudamericana",
        "nombre": "Copa Sudamericana",
        "categoria": "Futbol",
        "canales_default": ["ESPN 3", "DirecTV Sports 2"],
    },
    {
        "slug": "conmebol.recopa",
        "nombre": "Recopa Sudamericana",
        "categoria": "Futbol",
        "canales_default": ["ESPN", "DirecTV Sports"],
    },
    {
        "slug": "uefa.champions",
        "nombre": "Champions League",
        "categoria": "Futbol",
        "canales_default": ["ESPN", "ESPN 2"],
    },
    {
        "slug": "uefa.europa",
        "nombre": "Europa League",
        "categoria": "Futbol",
        "canales_default": ["ESPN 3", "ESPN 4"],
    },
    {
        "slug": "eng.1",
        "nombre": "Premier League",
        "categoria": "Futbol",
        "canales_default": ["ESPN", "ESPN 3"],
    },
    {
        "slug": "esp.1",
        "nombre": "La Liga",
        "categoria": "Futbol",
        "canales_default": ["ESPN 2", "DirecTV Sports"],
    },
    {
        "slug": "ger.1",
        "nombre": "Bundesliga",
        "categoria": "Futbol",
        "canales_default": ["ESPN 4", "ESPN 5"],
    },
    {
        "slug": "ita.1",
        "nombre": "Serie A",
        "categoria": "Futbol",
        "canales_default": ["ESPN", "ESPN 2"],
    },
    {
        "slug": "fra.1",
        "nombre": "Ligue 1",
        "categoria": "Futbol",
        "canales_default": ["ESPN 3"],
    },
    {
        "slug": "mex.1",
        "nombre": "Liga MX",
        "categoria": "Futbol",
        "canales_default": ["ESPN 2", "TUDN"],
    },
    {
        "slug": "arg.1",
        "nombre": "Liga Argentina",
        "categoria": "Futbol",
        "canales_default": ["TyC Sports", "ESPN"],
    },
    {
        "slug": "bra.1",
        "nombre": "Brasileirao",
        "categoria": "Futbol",
        "canales_default": ["Sport TV", "ESPN"],
    },
    {
        "slug": "usa.1",
        "nombre": "MLS",
        "categoria": "Futbol",
        "canales_default": ["ESPN 2"],
    },
    {
        "slug": "fifa.worldq.conmebol",
        "nombre": "Eliminatorias CONMEBOL",
        "categoria": "Futbol",
        "canales_default": ["RCN", "Caracol", "ESPN"],
    },
    {
        "slug": "fifa.world",
        "nombre": "Copa del Mundo",
        "categoria": "Futbol",
        "canales_default": ["RCN", "Caracol", "ESPN"],
    },
]


# ── Utilidades ─────────────────────────────────────────────────────────────────

def fetch_json(url: str):
    """Descarga un JSON desde una URL y lo retorna como dict/list, o None."""
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
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] No se pudo descargar {url}: {e}")
        return None


def normalizar(texto: str) -> str:
    """
    Normaliza un nombre de canal para comparacion flexible:
      - minusculas
      - sin acentos
      - 'Win Sports+' -> 'win sports plus'
      - elimina sufijos de pais: (Col), (Arg), (Lat), (Mex), etc.
      - elimina calidad: HD, SD, HD2, TDT
    """
    s = texto.lower().strip()
    # Remover acentos
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    # '+' -> ' plus'
    s = s.replace("+", " plus")
    # Quitar sufijos de pais entre parentesis
    s = re.sub(
        r"\s*\((col|arg|lat|mex|chi|us|usa|br|pe|uy|ec|ve|bo|py|ar)\)",
        "", s
    )
    # Quitar calidad
    s = re.sub(r"\b(hd2?|sd|tdt|4k)\b", "", s)
    # Comprimir espacios
    s = re.sub(r"\s+", " ", s).strip()
    return s


def construir_canales_map(cinestream_data: dict) -> dict:
    """
    Construye un mapa  nombre_normalizado -> url  a partir de cinestream.json.

    Prioridad al buscar canales duplicados (mismo nombre normalizado):
      1. Canales colombianos (contienen 'col' en el nombre original)
      2. Canales sin region especifica
      3. Otros paises
    """
    canales_raw = cinestream_data.get("canales", [])

    def prioridad(c: dict) -> int:
        name = c.get("name", "").lower()
        if "col" in name:
            return 0   # Colombia primero
        if not any(x in name for x in ["arg", "mex", "chi", "us)", "br)", "pe)", "uy)"]):
            return 1   # Sin region
        return 2       # Otra region

    canales_sorted = sorted(canales_raw, key=prioridad)

    canales_map = {}
    for c in canales_sorted:
        nombre = c.get("name", "").strip()
        url = c.get("url", "").strip()
        if not nombre or not url:
            continue
        norm = normalizar(nombre)
        if norm not in canales_map:          # Primera (mayor prioridad) gana
            canales_map[norm] = (nombre, url)

    print(f"  Canales cargados desde cinestream.json: {len(canales_map)}")
    return canales_map


def buscar_url_canal(nombre_buscar: str, canales_map: dict) -> tuple[str, str]:
    """
    Busca la URL de un canal por nombre en el mapa.
    Retorna (nombre_real, url) o ("", "") si no se encuentra.

    Estrategia de busqueda (en orden):
      1. Coincidencia exacta normalizada
      2. La clave del mapa empieza con el termino buscado
      3. El termino buscado empieza con la clave del mapa
      4. Uno contiene al otro
    """
    norm = normalizar(nombre_buscar)

    # 1. Exacto
    if norm in canales_map:
        return canales_map[norm]

    # 2. La clave del mapa empieza con el termino + espacio (ej: 'espn' busca 'espn 1')
    for key, val in canales_map.items():
        if key.startswith(norm + " "):
            return val

    # 3. El termino buscado empieza con la clave (ej: busco 'espn 2' y hay 'espn')
    for key, val in canales_map.items():
        if norm.startswith(key + " "):
            return val

    # 4. Contiene
    for key, val in canales_map.items():
        if norm in key or key in norm:
            return val

    return ("", "")


# ── Conversion de tiempo ───────────────────────────────────────────────────────

def utc_a_colombia(utc_str: str) -> tuple[str, str]:
    """
    Convierte fecha UTC de ESPN ('2026-04-17T21:00Z') a hora Colombia (UTC-5).
    Retorna ("2026-04-17", "16:00").
    """
    try:
        dt_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        dt_col = dt_utc.astimezone(TZ_COL)
        return dt_col.strftime("%Y-%m-%d"), dt_col.strftime("%H:%M")
    except Exception:
        return "", ""


# ── Obtencion de eventos ───────────────────────────────────────────────────────

def obtener_eventos_espn(canales_map: dict, hoy: str) -> list:
    """
    Consulta cada liga en la ESPN API y retorna los eventos de hoy
    en el formato nuevo de CineStream.
    """
    eventos = []

    for liga in LIGAS:
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{liga['slug']}/scoreboard"
        )
        print(f"  {liga['nombre']} ({liga['slug']})...")
        data = fetch_json(url)
        if not data:
            continue

        for event in data.get("events", []):
            fecha, hora = utc_a_colombia(event.get("date", ""))
            if fecha != hoy:
                continue

            # Equipos
            comp = (event.get("competitions") or [{}])[0]
            teams = comp.get("competitors", [])
            home = next((t for t in teams if t.get("homeAway") == "home"), {})
            away = next((t for t in teams if t.get("homeAway") == "away"), {})
            home_name = home.get("team", {}).get("displayName", "?")
            away_name = away.get("team", {}).get("displayName", "?")
            titulo = f"{liga['nombre']}: {home_name} vs {away_name}"

            # Construir canales con URLs reales de cinestream.json
            canales_evento = []
            for nombre_canal in liga["canales_default"]:
                real_nombre, url_canal = buscar_url_canal(nombre_canal, canales_map)
                if url_canal:
                    canales_evento.append({
                        "nombre": real_nombre or nombre_canal,
                        "iframe": url_canal,
                    })

            if not canales_evento:
                print(f"    [SKIP] Sin canales para: {titulo}")
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
    Lee eventos_extra.json y devuelve los de hoy (o sin fecha = en vivo).
    Ignora entradas de ejemplo/comentario (claves que empiezan con '_').
    """
    try:
        with open("eventos_extra.json", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []

    if not isinstance(raw, list):
        return []

    resultado = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if any(k.startswith("_") for k in item):
            continue
        fecha = item.get("fecha", "")
        if fecha and fecha != hoy:
            continue
        resultado.append(item)
    return resultado


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    hoy_col = datetime.now(TZ_COL).strftime("%Y-%m-%d")
    print(f"\n=== Generando agenda para {hoy_col} (hora Colombia) ===\n")

    # 1. Descargar cinestream.json y construir mapa de canales
    print("--- Cargando canales desde cinestream.json ---")
    cinestream_data = fetch_json(CINESTREAM_JSON_URL)
    if not cinestream_data:
        print("[ERROR] No se pudo descargar cinestream.json. Abortando.")
        return

    canales_map = construir_canales_map(cinestream_data)

    # 2. Eventos automaticos desde ESPN API
    print("\n--- ESPN API ---")
    eventos_espn = obtener_eventos_espn(canales_map, hoy_col)
    print(f"Eventos ESPN encontrados para hoy: {len(eventos_espn)}")

    # 3. Eventos manuales / extras
    print("\n--- Eventos manuales (eventos_extra.json) ---")
    eventos_manual = cargar_eventos_extra(hoy_col)
    print(f"Eventos manuales: {len(eventos_manual)}")

    # 4. Combinar (manuales primero, tienen prioridad) y ordenar por hora
    todos = eventos_manual + eventos_espn
    todos.sort(key=lambda e: e.get("hora", "99:99"))

    print(f"\nTotal eventos en agenda: {len(todos)}")

    # 5. Guardar agenda123.json
    with open("agenda123.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

    print(f"\nOK: agenda123.json generado con {len(todos)} eventos para {hoy_col}\n")
    for ev in todos:
        canales_str = ", ".join(c["nombre"] for c in ev.get("canales", []))
        print(f"  {ev.get('hora','?')} | {ev.get('titulo','?')}")
        print(f"          Canales: {canales_str}")


if __name__ == "__main__":
    main()
