import math
import os
import time
from collections import defaultdict, deque

import pandas as pd
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components

from nexus_client import NexusClient
from graph_builder import make_network_html

st.set_page_config(page_title="NexusDB AirRoute Resilience", layout="wide")
st.title("NexusDB — AirRoute Resilience V1.6.1 Multi-hop Route Explorer")
st.caption(
    "Demonstração de conectividade aérea em grafo: Airport, Route, Airline, Country e AircraftType."
)


def rows_as_dicts(cols, rows):
    return [
        {str(cols[i]): (row[i] if i < len(row) else "") for i in range(len(cols))}
        for row in rows
    ]


def val(d, *names):
    lower = {str(k).lower(): v for k, v in d.items()}
    for name in names:
        if name in d:
            return d[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return ""


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    vals = [fnum(lat1), fnum(lon1), fnum(lat2), fnum(lon2)]
    if any(v is None for v in vals):
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, vals)
    dlat, dlon = lat2-lat1, lon2-lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def run_query(nx, name, query, debug):
    try:
        cols, rows, payload = nx.query_rows(query)
        debug[name] = {"query": query, "processados": payload.get("processados")}
        return rows_as_dicts(cols, rows)
    except Exception as exc:
        debug[name] = {"query": query, "error": str(exc)}
        return []


def load_nexus(url, user, password, database, limit):
    """
    V1.2 Brasil-first:
    - carrega o catálogo de aeroportos brasileiros em consultas pequenas;
    - usa LOCATED_IN para descobrir Airport IDs do Brasil;
    - busca propriedades dos aeroportos em blocos leves;
    - carrega Route/Airline e relações para montar a vizinhança sob demanda.

    A consulta direta grande de Airport foi removida porque, no servidor
    testado, ela era a operação que provocava WinError 10035/10053.
    """
    nx = NexusClient(url, user, password, database)
    nx.authenticate_once()
    lim = int(limit)
    debug = {}

    # 1) Países e relação Airport->Country. Esta consulta funcionou no teste.
    country_rows = run_query(nx, "country_nodes", """
        MATCH (c:Country)
        RETURN c.name, c.iso_code
        LIMIT 1000
    """, debug)

    located = run_query(nx, "located_in", f"""
        MATCH (a:Airport)-[:LOCATED_IN]->(c:Country)
        RETURN a.airport_id, c.name, c.iso_code
        LIMIT {lim}
    """, debug)

    countries = {}
    for d in country_rows:
        cname = str(val(d, "c.name", "name") or "").strip()
        if cname:
            countries[cname] = {
                "name": cname,
                "iso_code": val(d, "c.iso_code", "iso_code")
            }

    # IDs brasileiros obtidos pela relação, evitando scan pesado de Airport.
    brazil_ids = set()
    country_by_airport = {}
    for d in located:
        aid = str(val(d, "a.airport_id", "airport_id") or "").strip()
        cname = str(val(d, "c.name", "name") or "").strip()
        iso = str(val(d, "c.iso_code", "iso_code") or "").strip()
        if aid:
            country_by_airport[aid] = (cname, iso)
        if aid and (iso.upper() == "BR" or cname.casefold() == "brazil"):
            brazil_ids.add(aid)

    # 2) Catálogo leve. Tentamos projeções pequenas, que reduzem a pressão no socket.
    # Se o scan ainda falhar, o dashboard continua com IDs e enriquece pelos endpoints
    # encontrados nas relações.
    airport_basic = run_query(nx, "airport_catalog", """
        MATCH (a:Airport)
        RETURN a.airport_id, a.name, a.iata, a.icao
        LIMIT 20000
    """, debug)

    airport_geo = run_query(nx, "airport_geo", """
        MATCH (a:Airport)
        RETURN a.airport_id, a.city, a.country, a.latitude, a.longitude
        LIMIT 20000
    """, debug)

    airports = {}
    for aid in brazil_ids:
        cname, iso = country_by_airport.get(aid, ("Brazil", "BR"))
        airports[aid] = {
            "airport_id": aid, "name": "", "city": "", "country": cname or "Brazil",
            "iata": "", "icao": "", "latitude": None, "longitude": None,
            "country_node": cname, "country_iso": iso,
        }

    def ensure_airport(aid):
        if not aid:
            return None
        if aid not in airports:
            cname, iso = country_by_airport.get(aid, ("", ""))
            airports[aid] = {
                "airport_id": aid, "name": "", "city": "", "country": cname,
                "iata": "", "icao": "", "latitude": None, "longitude": None,
                "country_node": cname, "country_iso": iso,
            }
        return airports[aid]

    for d in airport_basic:
        aid = str(val(d, "a.airport_id", "airport_id") or "").strip()
        if not aid:
            continue
        a = ensure_airport(aid)
        a["name"] = val(d, "a.name", "name")
        a["iata"] = val(d, "a.iata", "iata")
        a["icao"] = val(d, "a.icao", "icao")

    for d in airport_geo:
        aid = str(val(d, "a.airport_id", "airport_id") or "").strip()
        if not aid:
            continue
        a = ensure_airport(aid)
        a["city"] = val(d, "a.city", "city")
        a["country"] = val(d, "a.country", "country") or a.get("country")
        a["latitude"] = fnum(val(d, "a.latitude", "latitude"))
        a["longitude"] = fnum(val(d, "a.longitude", "longitude"))

    # V1.3: fonte principal para identificar Brasil = propriedade Airport.country.
    # LOCATED_IN continua sendo usada como evidência/materialização do grafo, mas
    # não pode bloquear a aplicação quando as relações HA estiverem incompletas.
    for aid, a in airports.items():
        country_text = str(a.get("country") or "").strip().casefold()
        country_node = str(a.get("country_node") or "").strip().casefold()
        iso = str(a.get("country_iso") or "").strip().upper()
        if country_text in ("brazil", "brasil") or country_node in ("brazil", "brasil") or iso == "BR":
            brazil_ids.add(aid)
            a["country_iso"] = a.get("country_iso") or "BR"
            a["country_node"] = a.get("country_node") or a.get("country") or "Brazil"

    debug["brazil_detection"] = {
        "airport_ids_detected": len(brazil_ids),
        "source": "Airport.country + LOCATED_IN/iso_code"
    }

    # 3) Rotas e companhias. Nós Route possuem source/destination, logo continuam
    # úteis mesmo se a materialização HA das arestas estiver incompleta.
    route_rows = run_query(nx, "route_nodes", f"""
        MATCH (r:Route)
        RETURN r.route_key, r.airline_code, r.source_airport_id,
               r.destination_airport_id, r.codeshare, r.stops, r.equipment
        LIMIT {lim}
    """, debug)

    airline_rows = run_query(nx, "airline_nodes", """
        MATCH (al:Airline)
        RETURN al.airline_id, al.name, al.iata, al.icao, al.country, al.active
        LIMIT 10000
    """, debug)

    airlines = {}
    airline_by_code = {}
    for d in airline_rows:
        alid = str(val(d, "al.airline_id", "airline_id") or "").strip()
        if not alid:
            continue
        obj = {
            "airline_id": alid,
            "name": val(d, "al.name", "name"),
            "iata": val(d, "al.iata", "iata"),
            "icao": val(d, "al.icao", "icao"),
            "country": val(d, "al.country", "country"),
            "active": val(d, "al.active", "active"),
        }
        airlines[alid] = obj
        for code in (obj.get("iata"), obj.get("icao")):
            if code and str(code) != "-":
                airline_by_code[str(code)] = alid

    routes = {}
    endpoint_ids = set()
    for d in route_rows:
        rk = str(val(d, "r.route_key", "route_key") or "").strip()
        src = str(val(d, "r.source_airport_id", "source_airport_id") or "").strip()
        dst = str(val(d, "r.destination_airport_id", "destination_airport_id") or "").strip()
        if not rk or not src or not dst:
            continue
        # Brasil-first: retenha somente rotas incidentes em aeroporto brasileiro.
        if src not in brazil_ids and dst not in brazil_ids:
            continue
        endpoint_ids.update((src, dst))
        airline_code = val(d, "r.airline_code", "airline_code")
        routes[rk] = {
            "route_key": rk, "source": src, "destination": dst,
            "airline_code": airline_code,
            "codeshare": val(d, "r.codeshare", "codeshare"),
            "stops": val(d, "r.stops", "stops"),
            "equipment": val(d, "r.equipment", "equipment"),
            "aircraft": [],
            "departure_edge": False, "arrival_edge": False, "operator_edge": False,
            "operator_id": airline_by_code.get(str(airline_code)) if airline_code else None,
        }

    # Garanta nós mínimos para destinos internacionais mesmo se o catálogo Airport
    # tiver sofrido falha de socket.
    for aid in endpoint_ids:
        ensure_airport(aid)

    # 4) Relações materializadas. Limitadas às consultas que já se mostraram estáveis.
    dep = run_query(nx, "departures", f"""
        MATCH (a:Airport)-[:DEPARTURE]->(r:Route)
        RETURN a.airport_id, r.route_key
        LIMIT {lim}
    """, debug)
    arr = run_query(nx, "arrivals", f"""
        MATCH (r:Route)-[:ARRIVAL]->(a:Airport)
        RETURN r.route_key, a.airport_id
        LIMIT {lim}
    """, debug)
    ops = run_query(nx, "operators", f"""
        MATCH (al:Airline)-[:OPERATES]->(r:Route)
        RETURN al.airline_id, r.route_key
        LIMIT {lim}
    """, debug)

    for d in dep:
        rk = str(val(d, "r.route_key", "route_key") or "").strip()
        if rk in routes:
            routes[rk]["departure_edge"] = True
    for d in arr:
        rk = str(val(d, "r.route_key", "route_key") or "").strip()
        if rk in routes:
            routes[rk]["arrival_edge"] = True
    for d in ops:
        rk = str(val(d, "r.route_key", "route_key") or "").strip()
        alid = str(val(d, "al.airline_id", "airline_id") or "").strip()
        if rk in routes:
            routes[rk]["operator_edge"] = True
            if alid:
                routes[rk]["operator_id"] = alid

    status = nx.cluster_status()
    return airports, routes, airlines, countries, status, debug

def build_indexes(airports, routes):
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    adjacency = defaultdict(set)
    for rk, r in routes.items():
        s, d = r.get("source"), r.get("destination")
        if not s or not d:
            continue
        outgoing[s].append(rk)
        incoming[d].append(rk)
        adjacency[s].add(d)
    return outgoing, incoming, adjacency


def shortest_path(adjacency, source, target, removed=None):
    removed = set(removed or [])
    if source in removed or target in removed:
        return None
    q = deque([(source, [source])])
    seen = {source}
    while q:
        node, path = q.popleft()
        if node == target:
            return path
        for nxt in adjacency.get(node, set()):
            if nxt not in seen and nxt not in removed:
                seen.add(nxt)
                q.append((nxt, path + [nxt]))
    return None


def airport_label(a):
    code = a.get("iata") or a.get("icao") or a.get("airport_id")
    return f"{code} — {a.get('name','')} ({a.get('city','')}, {a.get('country','')})"


def analyze_airport(selected_id, airports, routes, airlines):
    outgoing, incoming, adjacency = build_indexes(airports, routes)
    incident = list(dict.fromkeys(outgoing.get(selected_id, []) + incoming.get(selected_id, [])))
    neighbors = set()
    operator_ids = set()
    known_operator = 0
    inferred_operator = 0
    unknown_operator = 0
    affected_countries = set()
    total_km = 0.0
    km_count = 0

    for rk in incident:
        r = routes[rk]
        other = r["destination"] if r["source"] == selected_id else r["source"]
        if other:
            neighbors.add(other)
            if other in airports:
                affected_countries.add(airports[other].get("country") or "")
        if r.get("operator_edge") and r.get("operator_id") and r["operator_id"] in airlines:
            known_operator += 1
            operator_ids.add(r["operator_id"])
        elif r.get("operator_id") and r["operator_id"] in airlines:
            inferred_operator += 1
            operator_ids.add(r["operator_id"])
        else:
            unknown_operator += 1

        a = airports.get(r["source"], {})
        b = airports.get(r["destination"], {})
        dist = haversine_km(a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude"))
        if dist is not None:
            total_km += dist
            km_count += 1

    # "Conectividade conhecida" = rota possui origem+destino.
    # "Operador identificado" = existe Airline-[:OPERATES]->Route.
    total = len(incident)
    operator_coverage = (known_operator / total * 100) if total else 0
    inferred_coverage = (inferred_operator / total * 100) if total else 0

    # Proxy simples de centralidade local para demo.
    degree = len(set(outgoing.get(selected_id, []) + incoming.get(selected_id, [])))
    max_degree = max(
        [len(set(outgoing.get(aid, []) + incoming.get(aid, []))) for aid in airports] or [1]
    )
    degree_score = degree / max_degree if max_degree else 0

    return {
        "incident_routes": incident,
        "outgoing_routes": outgoing.get(selected_id, []),
        "incoming_routes": incoming.get(selected_id, []),
        "neighbors": neighbors,
        "operator_ids": operator_ids,
        "known_operator": known_operator,
        "inferred_operator": inferred_operator,
        "unknown_operator": unknown_operator,
        "operator_coverage": operator_coverage,
        "inferred_coverage": inferred_coverage,
        "affected_countries": {c for c in affected_countries if c},
        "degree": degree,
        "degree_score": degree_score,
        "avg_route_km": (total_km/km_count if km_count else 0),
        "adjacency": adjacency,
    }


def map_dataframe(airports, routes, route_keys, selected_id):
    rows = []
    for rk in route_keys:
        r = routes.get(rk, {})
        a = airports.get(r.get("source"), {})
        b = airports.get(r.get("destination"), {})
        if None in (a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")):
            continue
        operator_materialized = bool(r.get("operator_edge"))
        operator_inferred = (not operator_materialized) and bool(r.get("operator_id"))
        if operator_materialized:
            operator_status = "OPERATES materializado"
            route_color = [34, 197, 94, 180]
        elif operator_inferred:
            operator_status = "Operador inferido por airline_code"
            route_color = [59, 130, 246, 180]
        else:
            operator_status = "Conectividade conhecida / operador não resolvido"
            route_color = [245, 158, 11, 190]
        rows.append({
            "route_key": rk,
            "source": a.get("iata") or a.get("icao") or a.get("name"),
            "destination": b.get("iata") or b.get("icao") or b.get("name"),
            "source_lat": a["latitude"], "source_lon": a["longitude"],
            "dest_lat": b["latitude"], "dest_lon": b["longitude"],
            "operator_status": operator_status,
            "color": route_color,
        })
    return pd.DataFrame(rows)




def unwrap_native_payload(payload):
    """Normaliza o envelope HTTP sem alterar o resultado produzido pelo CALL."""
    if not isinstance(payload, dict):
        return payload
    rows = payload.get("resultados")
    if (
        isinstance(rows, list)
        and len(rows) == 1
        and isinstance(rows[0], dict)
        and ("algorithm" in rows[0] or "resultados" in rows[0])
    ):
        return rows[0]
    return payload


def native_call(nx, query):
    """Executa uma query no servidor e mede o tempo observado pelo cliente."""
    t0 = time.perf_counter()
    try:
        raw = nx.query_payload(query)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if not isinstance(raw, dict):
            return None, f"Resposta inesperada: {type(raw).__name__}", elapsed_ms
        errors = raw.get("errors") or []
        if errors:
            return None, str(errors), elapsed_ms
        payload = unwrap_native_payload(raw)
        if isinstance(payload, dict) and payload.get("status") in ("error", "failed"):
            return None, str(payload.get("error") or payload), elapsed_ms
        return payload, None, elapsed_ms
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return None, str(exc), elapsed_ms


def node_props(row):
    n = row.get("node") if isinstance(row, dict) else None
    if not isinstance(n, dict):
        return {}
    props = n.get("properties")
    return props if isinstance(props, dict) else {}


def find_native_node_id(rows, airport_id):
    for row in rows or []:
        p = node_props(row)
        if str(p.get("airport_id", "")) == str(airport_id):
            return row.get("node_id") or (row.get("node") or {}).get("id")
    return None


def format_ms(ms):
    if ms is None:
        return "—"
    return f"{ms:,.1f} ms" if ms < 1000 else f"{ms/1000:,.3f} s"


def run_native_analytics(url, user, password, database, pagerank_iterations=20):
    """
    V1.5: todos os algoritmos abaixo são CALL server-side.
    Degree usa LIMIT amplo para também funcionar como mapa airport_id -> node_id;
    a UI exibe apenas o top 20.
    """
    nx = NexusClient(url, user, password, database)
    calls = {
        "degree": "CALL algo.degree() LIMIT 20000",
        "pagerank": f"CALL algo.pageRank({int(pagerank_iterations)}) LIMIT 200",
        "components": "CALL algo.connectedComponents()",
        "statistics": "CALL graph.statistics()",
    }
    result = {}
    for key, query in calls.items():
        payload, err, elapsed_ms = native_call(nx, query)
        result[key] = {
            "payload": payload,
            "error": err,
            "query": query,
            "elapsed_ms": elapsed_ms,
            "engine": "NexusDB / CSR",
        }
    return nx, result


def spatial_query(nx, lat, lon, radius_km, limit=500):
    """
    ST_DWithin é executado no NexusDB/RTree.
    Na implementação atual, SRID 4326 usa unidade angular no predicado nativo;
    km/111.32 produz o raio angular aproximado do pré-filtro. Haversine apenas
    refina os candidatos retornados para a apresentação em quilômetros.
    """
    if lat is None or lon is None:
        return [], "Aeroporto sem latitude/longitude.", None, None

    degrees = float(radius_km) / 111.32
    query = (
        f"MATCH (a:Airport) WHERE ST_DWithin(a, "
        f"{float(lon)}, {float(lat)}, {degrees}) RETURN a LIMIT {int(limit)}"
    )
    payload, err, elapsed_ms = native_call(nx, query)
    if err:
        return [], err, query, elapsed_ms

    rows = (payload or {}).get("resultados", []) if isinstance(payload, dict) else []
    out = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
        alat, alon = fnum(props.get("latitude")), fnum(props.get("longitude"))
        d = haversine_km(lat, lon, alat, alon)
        if d is not None and d <= radius_km + 1e-9:
            out.append({
                "airport_id": props.get("airport_id"),
                "iata": props.get("iata"),
                "icao": props.get("icao"),
                "name": props.get("name"),
                "city": props.get("city"),
                "country": props.get("country"),
                "latitude": alat,
                "longitude": alon,
                "distance_km": d,
                "node_id": item.get("id"),
            })
    out.sort(key=lambda x: x["distance_km"])
    return out, None, query, elapsed_ms


def execute_native_shortest_path(nx, source_node_id, target_node_id):
    query = f"CALL algo.shortestPath({int(source_node_id)}, {int(target_node_id)})"
    payload, err, elapsed_ms = native_call(nx, query)
    return {
        "payload": payload,
        "error": err,
        "elapsed_ms": elapsed_ms,
        "query": query,
        "engine": "NexusDB / CSR",
    }


def native_path_labels(payload):
    """Converte o path retornado pelo NexusDB em rótulos amigáveis."""
    if not isinstance(payload, dict) or not payload.get("found"):
        return []
    results = payload.get("resultados") or []
    if not results or not isinstance(results[0], dict):
        return []
    nodes = results[0].get("path") or []
    labels = []
    for node in nodes:
        props = node.get("properties", {}) if isinstance(node, dict) else {}
        labels.append(
            props.get("iata")
            or props.get("icao")
            or props.get("name")
            or props.get("route_key")
            or props.get("airline_code")
            or f"#{node.get('id') if isinstance(node, dict) else '?'}"
        )
    return labels


def airport_is_usable(a):
    return bool(a and a.get("airport_id") and (a.get("name") or a.get("iata") or a.get("icao")))


def all_airport_candidates(airports, outgoing, incoming):
    rows = [
        a for aid, a in airports.items()
        if airport_is_usable(a) and (outgoing.get(aid) or incoming.get(aid))
    ]
    rows.sort(key=lambda a: (
        str(a.get("country") or ""),
        str(a.get("city") or ""),
        str(a.get("name") or ""),
        str(a.get("iata") or ""),
    ))
    return rows


def airport_country(a):
    return str((a or {}).get("country") or (a or {}).get("country_node") or "").strip()


def route_adjacency(routes):
    """Airport-level directed adjacency reconstructed from Route properties."""
    adj = {}
    edge_routes = {}
    for rk, r in routes.items():
        s, d = str(r.get("source") or ""), str(r.get("destination") or "")
        if not s or not d:
            continue
        adj.setdefault(s, set()).add(d)
        edge_routes.setdefault((s, d), []).append(r)
    return adj, edge_routes


def enumerate_airport_paths(routes, source_id, target_ids, max_legs=4, max_paths=100):
    """
    Enumerates simple Airport→Airport paths using Route.source/destination.
    This is the semantic flight-route view. It intentionally avoids traversing
    Country/Airline/AircraftType nodes, which are part of the heterogeneous CSR.
    """
    adj, edge_routes = route_adjacency(routes)
    target_ids = set(str(x) for x in target_ids)
    found = []
    queue = [(str(source_id), [str(source_id)])]

    while queue and len(found) < max_paths:
        cur, path = queue.pop(0)
        legs = len(path) - 1
        if legs >= max_legs:
            continue
        for nxt in sorted(adj.get(cur, ())):
            if nxt in path:
                continue
            np = path + [nxt]
            if nxt in target_ids:
                found.append(np)
                if len(found) >= max_paths:
                    break
            if len(np) - 1 < max_legs:
                queue.append((nxt, np))

    def path_detail(path):
        legs = []
        total_km = 0.0
        for a, b in zip(path, path[1:]):
            rs = edge_routes.get((a, b), [])
            operators = sorted({
                str(r.get("airline_code"))
                for r in rs if r.get("airline_code")
            })
            legs.append({"source": a, "destination": b, "routes": rs, "operators": operators})
        return {"airports": path, "legs": legs}

    return [path_detail(p) for p in found]


def path_distance_km(path, airports):
    total = 0.0
    for a, b in zip(path, path[1:]):
        aa, bb = airports.get(a), airports.get(b)
        if not aa or not bb:
            return None
        d = haversine_km(aa.get("latitude"), aa.get("longitude"),
                         bb.get("latitude"), bb.get("longitude"))
        if d is None:
            return None
        total += d
    return total


def path_country_sequence(path, airports):
    seq = []
    for aid in path:
        c = airport_country(airports.get(aid))
        if c and (not seq or seq[-1] != c):
            seq.append(c)
    return seq


def friendly_path(path, airports):
    labels = []
    for aid in path:
        a = airports.get(aid, {})
        labels.append(str(a.get("iata") or a.get("icao") or a.get("name") or aid))
    return " → ".join(labels)


def build_route_explorer_map(paths, airports, selected_index=0, show_all=False):
    """Mostra por padrão apenas o itinerário selecionado."""
    if not paths or selected_index < 0 or selected_index >= len(paths):
        return None

    selected_path = paths[selected_index]
    visible = list(enumerate(paths)) if show_all else [(selected_index, selected_path)]
    arc_rows, points = [], {}

    for pi, item in visible:
        path = item["airports"]
        is_selected = pi == selected_index
        for aid in path:
            a = airports.get(aid)
            if a and a.get("latitude") is not None and a.get("longitude") is not None:
                points[aid] = a
        for leg_no, (a_id, b_id) in enumerate(zip(path, path[1:]), 1):
            a, b = airports.get(a_id), airports.get(b_id)
            if not a or not b or None in (
                a.get("latitude"), a.get("longitude"),
                b.get("latitude"), b.get("longitude")
            ):
                continue
            arc_rows.append({
                "source_lon": a["longitude"], "source_lat": a["latitude"],
                "target_lon": b["longitude"], "target_lat": b["latitude"],
                "path_no": pi + 1, "leg_no": leg_no,
                "route_label": friendly_path(path, airports),
                "leg_label": f"{a.get('iata') or a_id} → {b.get('iata') or b_id}",
                "color": [34, 197, 94, 225] if is_selected else [59, 130, 246, 65],
                "width": 5 if is_selected else 2,
            })

    if not arc_rows:
        return None

    center_lat = sum(x["latitude"] for x in points.values()) / len(points)
    center_lon = sum(x["longitude"] for x in points.values()) / len(points)
    selected_ids = set(selected_path["airports"])
    point_rows = [{
        "lon": a["longitude"], "lat": a["latitude"],
        "name": a.get("name"), "iata": a.get("iata"), "country": a.get("country"),
        "radius": 55000 if aid in selected_ids else 26000,
    } for aid, a in points.items()]

    return pdk.Deck(
        layers=[
            pdk.Layer("ArcLayer", data=arc_rows,
                      get_source_position="[source_lon, source_lat]",
                      get_target_position="[target_lon, target_lat]",
                      get_source_color="color", get_target_color="color",
                      get_width="width", pickable=True),
            pdk.Layer("ScatterplotLayer", data=point_rows,
                      get_position="[lon, lat]", get_radius="radius", pickable=True),
        ],
        initial_view_state=pdk.ViewState(
            latitude=center_lat, longitude=center_lon, zoom=2.4
        ),
        tooltip={"html": "<b>{leg_label}</b><br/>{route_label}<br/>"
                         "<b>{iata}</b> {name}<br/>{country}"},
    )

with st.sidebar:
    st.header("NexusDB")
    url = st.text_input("URL", value=os.getenv("NEXUSDB_URL", "http://127.0.0.1:7475"))
    database = st.text_input("Database", value=os.getenv("NEXUSDB_DATABASE", "OPENFLIGHTS_TEST"))
    user = st.text_input("Usuário", value=os.getenv("NEXUSDB_USER", "admin"))
    password = st.text_input("Senha", type="password")
    limit = st.number_input("Máximo de rotas/relações", 5000, 200000, 80000, 5000)
    connect = st.button("Conectar / carregar grafo", type="primary", use_container_width=True)

    if st.session_state.get("air_loaded"):
        st.success("Grafo carregado em memória.")
        if st.button("Desconectar / limpar sessão", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("air_"):
                    del st.session_state[k]
            st.rerun()

if connect:
    if not password:
        st.error("Informe a senha.")
        st.stop()
    with st.spinner("Autenticando e carregando o grafo do NexusDB..."):
        try:
            data = load_nexus(url, user, password, database, int(limit))
        except Exception as exc:
            st.error(f"Falha: {exc}")
            st.stop()
    airports, routes, airlines, countries, status, debug = data
    st.session_state["air_airports"] = airports
    st.session_state["air_routes"] = routes
    st.session_state["air_airlines"] = airlines
    st.session_state["air_countries"] = countries
    st.session_state["air_status"] = status
    st.session_state["air_debug"] = debug
    st.session_state["air_conn"] = {
        "url": url, "user": user, "password": password, "database": database
    }
    st.session_state["air_loaded"] = True

if not st.session_state.get("air_loaded"):
    st.info("Informe a conexão e clique em “Conectar / carregar grafo”.")
    st.stop()

airports = st.session_state["air_airports"]
routes = st.session_state["air_routes"]
airlines = st.session_state["air_airlines"]
countries = st.session_state["air_countries"]
status = st.session_state.get("air_status", {})
debug = st.session_state.get("air_debug", {})

st.success(
    f"NexusDB Brasil-first — {len(airports):,} aeroportos carregados · {len(routes):,} rotas relacionadas ao Brasil · "
    f"{len(airlines):,} companhias cadastradas · {len(countries):,} países/territórios"
)

with st.expander("Diagnóstico NexusDB / consultas"):
    st.json({"cluster_status": status, "queries": debug})

outgoing, incoming, adjacency = build_indexes(airports, routes)
candidates = [
    a for aid, a in airports.items()
    if (outgoing.get(aid) or incoming.get(aid))
    and (
        str(a.get("country_iso") or "").upper() == "BR"
        or str(a.get("country") or "").casefold() == "brazil"
        or str(a.get("country_node") or "").casefold() == "brazil"
    )
]

def brazil_sort_key(a):
    code = str(a.get("iata") or a.get("icao") or "")
    # GIG/SDU primeiro para uma abertura natural no Brasil/Rio; depois alfabético.
    priority = {"GIG": 0, "SDU": 1, "GRU": 2, "CGH": 3, "BSB": 4}.get(code, 50)
    return (priority, str(a.get("city") or ""), str(a.get("name") or ""), str(a.get("airport_id")))

candidates.sort(key=brazil_sort_key)

left, right = st.columns([0.34, 0.66], gap="large")

with left:
    st.subheader("Aeroporto e conectividade")
    if not candidates:
        brdiag = debug.get("brazil_detection", {})
        st.error(
            "Nenhuma rota brasileira utilizável foi encontrada. "
            f"Aeroportos identificados como Brasil: {brdiag.get('airport_ids_detected', 0)}. "
            "Abra “Diagnóstico NexusDB / consultas” e verifique `airport_geo`, "
            "`brazil_detection` e `route_nodes`."
        )
        st.stop()
    default_index = 0
    for i, a in enumerate(candidates):
        if str(a.get("iata") or "").upper() == "GIG":
            default_index = i
            break
    selected = st.selectbox(
        "Aeroporto de partida no Brasil",
        candidates,
        index=default_index,
        format_func=airport_label,
    )
    selected_id = selected["airport_id"]
    analysis = analyze_airport(selected_id, airports, routes, airlines)

    c1, c2 = st.columns(2)
    c1.metric("Rotas incidentes", f"{len(analysis['incident_routes']):,}")
    c2.metric("Aeroportos conectados", f"{len(analysis['neighbors']):,}")
    c1.metric("Saídas", f"{len(analysis['outgoing_routes']):,}")
    c2.metric("Chegadas", f"{len(analysis['incoming_routes']):,}")
    c1.metric("Companhias identificadas", f"{len(analysis['operator_ids']):,}")
    c2.metric("Países alcançados", f"{len(analysis['affected_countries']):,}")

    st.markdown("#### Qualidade semântica da conectividade")
    st.progress(min(analysis["operator_coverage"]/100, 1.0))
    st.write(
        f"**{analysis['known_operator']:,}** com `OPERATES` materializado "
        f"({analysis['operator_coverage']:.1f}%) · "
        f"**{analysis['inferred_operator']:,}** com operador inferido por `Route.airline_code` "
        f"({analysis['inferred_coverage']:.1f}%) · "
        f"**{analysis['unknown_operator']:,}** sem operador resolvido."
    )

    st.markdown("#### Geoespacial")
    st.write(
        f"Distância média das rotas incidentes: **{analysis['avg_route_km']:,.0f} km**. "
        "O mapa usa latitude/longitude armazenadas nos nós `Airport`; a distância é calculada "
        "pela aplicação com Haversine para manter compatibilidade com a API atual."
    )

    simulate = st.checkbox("Simular aeroporto indisponível", value=False)
    focus_graph = st.checkbox("Grafo: mostrar somente vizinhança selecionada", value=True)

with right:
    st.subheader("Mapa geoespacial das conexões")
    map_df = map_dataframe(airports, routes, analysis["incident_routes"], selected_id)
    if not map_df.empty:
        center_lat = selected.get("latitude") or map_df["source_lat"].mean()
        center_lon = selected.get("longitude") or map_df["source_lon"].mean()

        arc = pdk.Layer(
            "ArcLayer",
            data=map_df,
            get_source_position=["source_lon", "source_lat"],
            get_target_position=["dest_lon", "dest_lat"],
            get_source_color="color",
            get_target_color="color",
            get_width=2,
            pickable=True,
            auto_highlight=True,
        )

        airport_points = []
        ids_for_points = {selected_id} | analysis["neighbors"]
        for aid in ids_for_points:
            a = airports.get(aid, {})
            if a.get("latitude") is not None and a.get("longitude") is not None:
                airport_points.append({
                    "name": airport_label(a),
                    "lat": a["latitude"], "lon": a["longitude"],
                    "selected": aid == selected_id,
                    "radius": 50000 if aid == selected_id else 25000,
                    "color": [239, 68, 68, 220] if aid == selected_id else [59, 130, 246, 180],
                })
        point_df = pd.DataFrame(airport_points)
        scatter = pdk.Layer(
            "ScatterplotLayer",
            data=point_df,
            get_position=["lon", "lat"],
            get_radius="radius",
            get_fill_color="color",
            pickable=True,
        )
        deck = pdk.Deck(
            layers=[arc, scatter],
            initial_view_state=pdk.ViewState(
                latitude=float(center_lat), longitude=float(center_lon), zoom=2.2, pitch=20
            ),
            tooltip={"text": "{source} → {destination}\n{operator_status}"},
        )
        st.pydeck_chart(deck, use_container_width=True)
        st.caption("Verde: `OPERATES` materializado · azul: operador inferido por `airline_code` · âmbar: operador não resolvido.")
    else:
        st.warning("As rotas selecionadas não possuem coordenadas suficientes para o mapa.")


st.divider()
st.subheader("NexusDB V1.5 — CSR Native Analytics + Geospatial")
st.caption(
    "Degree, PageRank, Connected Components e Shortest Path são executados no servidor NexusDB "
    "pelo caminho data.rs → graph_routes.rs → graph_algorithms.rs → CSR. "
    "Os tempos abaixo são tempos observados pelo cliente HTTP e incluem transporte/serialização."
)

conn = st.session_state.get("air_conn", {})
analytics_col, geo_col = st.columns(2, gap="large")

with analytics_col:
    st.markdown("#### Graph Analytics no NexusDB / CSR")
    pr_iterations = st.number_input("Iterações do PageRank", 1, 100, 20, 1)

    if st.button("Executar Degree + PageRank + Components", use_container_width=True):
        with st.spinner("Executando algoritmos no NexusDB/CSR..."):
            try:
                _, native = run_native_analytics(
                    conn["url"], conn["user"], conn["password"], conn["database"],
                    pagerank_iterations=int(pr_iterations),
                )
                st.session_state["air_native"] = native
            except Exception as exc:
                st.error(str(exc))

    native = st.session_state.get("air_native")
    if native:
        degree = native["degree"]
        pagerank = native["pagerank"]
        components_result = native["components"]
        statistics = native["statistics"]

        degree_rows = ((degree.get("payload") or {}).get("resultados") or [])
        pr_rows = ((pagerank.get("payload") or {}).get("resultados") or [])
        cc_payload = components_result.get("payload") or {}
        cc_rows = cc_payload.get("resultados") or []

        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Degree", format_ms(degree.get("elapsed_ms")))
        t2.metric("PageRank", format_ms(pagerank.get("elapsed_ms")))
        t3.metric("Components", format_ms(components_result.get("elapsed_ms")))
        t4.metric("Statistics", format_ms(statistics.get("elapsed_ms")))

        m1, m2, m3 = st.columns(3)
        selected_degree = next(
            (r.get("degree") for r in degree_rows
             if str(node_props(r).get("airport_id", "")) == str(selected_id)),
            None
        )
        selected_rank = next(
            (r.get("score") for r in pr_rows
             if str(node_props(r).get("airport_id", "")) == str(selected_id)),
            None
        )
        m1.metric("Degree do aeroporto", selected_degree if selected_degree is not None else "—")
        m2.metric(
            "PageRank do aeroporto",
            f"{selected_rank:.6g}" if isinstance(selected_rank, (int, float)) else "fora do top 200"
        )
        m3.metric("Componentes conectados", cc_payload.get("components", len(cc_rows)))

        if cc_rows:
            largest = max((int(r.get("size", 0)) for r in cc_rows if isinstance(r, dict)), default=0)
            st.write(f"**Maior componente conectado:** {largest:,} nós.")

        stat_payload = statistics.get("payload") or {}
        stat_rows = stat_payload.get("resultados") or []
        if stat_rows and isinstance(stat_rows[0], dict):
            s = stat_rows[0]
            st.caption(
                f"Grafo materializado no servidor: {s.get('nodes','?')} nós · "
                f"{s.get('relationships','?')} relações · "
                f"grau médio {float(s.get('average_degree',0) or 0):.2f} · "
                f"maior componente {s.get('largest_component','?')}."
            )

        with st.expander("Resultados, queries CALL e tempos"):
            st.markdown("**Queries efetivamente enviadas ao NexusDB**")
            perf_rows = []
            for key in ("degree", "pagerank", "components", "statistics"):
                item = native[key]
                perf_rows.append({
                    "Operação": key,
                    "Engine": item.get("engine"),
                    "Query": item.get("query"),
                    "Tempo cliente": format_ms(item.get("elapsed_ms")),
                    "Status": "OK" if not item.get("error") else "ERRO",
                })
            st.dataframe(pd.DataFrame(perf_rows), hide_index=True, use_container_width=True)

            if degree_rows:
                st.markdown("**Top 20 Degree — grafo completo**")
                st.dataframe(pd.DataFrame([{
                    "node_id": r.get("node_id"),
                    "label": (r.get("node") or {}).get("label"),
                    "nó": node_props(r).get("iata")
                          or node_props(r).get("name")
                          or node_props(r).get("route_key")
                          or node_props(r).get("airport_id"),
                    "degree": r.get("degree"),
                } for r in degree_rows[:20]]), hide_index=True, use_container_width=True)

            airport_degree_rows = [
                r for r in degree_rows
                if str((r.get("node") or {}).get("label", "")).casefold() == "airport"
            ]
            if airport_degree_rows:
                st.markdown("**Top 20 Degree — somente Airport (filtro de apresentação)**")
                st.dataframe(pd.DataFrame([{
                    "node_id": r.get("node_id"),
                    "IATA": node_props(r).get("iata"),
                    "Aeroporto": node_props(r).get("name"),
                    "degree": r.get("degree"),
                } for r in airport_degree_rows[:20]]), hide_index=True, use_container_width=True)

            if pr_rows:
                st.markdown("**Top 20 PageRank — grafo completo**")
                st.dataframe(pd.DataFrame([{
                    "node_id": r.get("node_id"),
                    "label": (r.get("node") or {}).get("label"),
                    "nó": node_props(r).get("iata")
                          or node_props(r).get("name")
                          or node_props(r).get("route_key")
                          or node_props(r).get("airport_id"),
                    "score": r.get("score"),
                } for r in pr_rows[:20]]), hide_index=True, use_container_width=True)

            airport_pr_rows = [
                r for r in pr_rows
                if str((r.get("node") or {}).get("label", "")).casefold() == "airport"
            ]
            if airport_pr_rows:
                st.markdown("**PageRank — Airport presentes no Top 200 global**")
                st.dataframe(pd.DataFrame([{
                    "node_id": r.get("node_id"),
                    "IATA": node_props(r).get("iata"),
                    "Aeroporto": node_props(r).get("name"),
                    "score": r.get("score"),
                } for r in airport_pr_rows[:20]]), hide_index=True, use_container_width=True)

            st.caption(
                "Os algoritmos continuam sendo executados no NexusDB/CSR sobre o grafo completo. "
                "Os filtros 'somente Airport' acima são apenas de apresentação no dashboard."
            )

            for key, item in native.items():
                if item.get("error"):
                    st.warning(f"{key}: {item['error']}")

with geo_col:
    st.markdown("#### Geospatial nativo — ST_DWithin / RTree")
    radius_km = st.slider("Aeroportos em um raio de", 50, 1500, 500, 50, format="%d km")

    if st.button("Consultar raio no NexusDB", use_container_width=True):
        nx_geo = NexusClient(conn["url"], conn["user"], conn["password"], conn["database"])
        with st.spinner("Executando ST_DWithin no índice espacial do NexusDB..."):
            near, geo_err, geo_query, geo_ms = spatial_query(
                nx_geo,
                selected.get("latitude"),
                selected.get("longitude"),
                radius_km,
                500,
            )
        st.session_state["air_near"] = near
        st.session_state["air_geo_err"] = geo_err
        st.session_state["air_geo_query"] = geo_query
        st.session_state["air_geo_ms"] = geo_ms
        st.session_state["air_geo_radius"] = radius_km

    if st.session_state.get("air_geo_err"):
        st.warning(st.session_state["air_geo_err"])

    near = st.session_state.get("air_near", [])
    if st.session_state.get("air_geo_query"):
        g1, g2 = st.columns(2)
        g1.metric("Tempo ST_DWithin", format_ms(st.session_state.get("air_geo_ms")))
        g2.metric("Aeroportos no raio", len(near))
        st.code(st.session_state["air_geo_query"], language="cypher")

    if near:
        st.dataframe(pd.DataFrame([{
            "IATA": x.get("iata"),
            "Aeroporto": x.get("name"),
            "Cidade": x.get("city"),
            "País": x.get("country"),
            "Distância km": round(x["distance_km"], 1),
        } for x in near]), hide_index=True, use_container_width=True)
        st.caption(
            "ST_DWithin/RTree seleciona os candidatos no NexusDB. "
            "Como a implementação atual trabalha em coordenadas SRID 4326, o dashboard converte "
            "o raio km→graus para o pré-filtro e usa Haversine apenas para refinar/exibir km."
        )

tabs = st.tabs(["Rede", "Conectividade", "Companhias", "Impacto / Resiliência", "Caminhos", "Planejador Multi-hop"])

with tabs[0]:
    st.subheader("Property graph")
    html = make_network_html(
        airports, routes, airlines, countries,
        selected_id=selected_id,
        focus_only=focus_graph,
        removed_id=selected_id if simulate else None,
    )
    components.html(html, height=760, scrolling=True)

with tabs[1]:
    st.subheader("Conectividade conhecida × operador identificado")
    records = []
    for rk in analysis["incident_routes"]:
        r = routes[rk]
        src = airports.get(r["source"], {})
        dst = airports.get(r["destination"], {})
        op = airlines.get(r.get("operator_id"), {})
        dist = haversine_km(src.get("latitude"), src.get("longitude"), dst.get("latitude"), dst.get("longitude"))
        records.append({
            "Origem": src.get("iata") or src.get("icao") or src.get("name"),
            "Destino": dst.get("iata") or dst.get("icao") or dst.get("name"),
            "Conectividade": "Conhecida",
            "Operador": op.get("name") or "Não identificado",
            "Código": r.get("airline_code") or "",
            "Distância km": round(dist, 1) if dist is not None else None,
            "Equipamento": r.get("equipment") or "",
            "Route": rk,
        })
    rdf = pd.DataFrame(records)
    st.dataframe(rdf, use_container_width=True, hide_index=True)
    st.caption(
        "Uma rota permanece uma evidência de conectividade mesmo quando não há uma aresta "
        "`Airline-[:OPERATES]->Route`. Isso demonstra schema flexível sem descartar informação parcial."
    )

with tabs[2]:
    st.subheader("Empresas aéreas relacionadas ao aeroporto")
    op_rows = []
    for alid in sorted(analysis["operator_ids"]):
        a = airlines.get(alid, {})
        count = sum(1 for rk in analysis["incident_routes"] if routes[rk].get("operator_id") == alid)
        op_rows.append({
            "Companhia": a.get("name"),
            "IATA": a.get("iata"),
            "ICAO": a.get("icao"),
            "País": a.get("country"),
            "Ativa": a.get("active"),
            "Rotas incidentes": count,
        })
    st.dataframe(
        pd.DataFrame(op_rows).sort_values("Rotas incidentes", ascending=False) if op_rows else pd.DataFrame(),
        use_container_width=True, hide_index=True
    )

with tabs[3]:
    st.subheader("Simulação de indisponibilidade")
    if not simulate:
        st.info("Marque “Simular aeroporto indisponível” para visualizar o impacto.")
    else:
        st.error(f"Simulação: {airport_label(selected)} indisponível.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rotas interrompidas", len(analysis["incident_routes"]))
        c2.metric("Aeroportos afetados", len(analysis["neighbors"]))
        c3.metric("Companhias afetadas", len(analysis["operator_ids"]))
        c4.metric("Países afetados", len(analysis["affected_countries"]))

        alt_rows = []
        for nid in sorted(analysis["neighbors"]):
            target = airports.get(nid, {})
            # Procura caminho entre vizinhos sem passar pelo aeroporto removido.
            alternatives = []
            for other in analysis["neighbors"]:
                if other == nid:
                    continue
                p = shortest_path(analysis["adjacency"], other, nid, removed={selected_id})
                if p and len(p) <= 4:
                    alternatives.append(p)
            alt_rows.append({
                "Aeroporto afetado": airport_label(target),
                "Alternativa curta sem aeroporto removido": "Sim" if alternatives else "Não encontrada em até 3 saltos",
                "Exemplo": " → ".join(
                    (airports[x].get("iata") or airports[x].get("icao") or x)
                    for x in alternatives[0]
                ) if alternatives else "",
            })
        st.dataframe(pd.DataFrame(alt_rows), use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Shortest path demonstrativo")
    targets = [airports[n] for n in analysis["neighbors"] if n in airports]
    if targets:
        target = st.selectbox("Destino conectado", targets, format_func=airport_label)
        p1 = shortest_path(adjacency, selected_id, target["airport_id"])
        p2 = shortest_path(adjacency, selected_id, target["airport_id"], removed={selected_id}) if simulate else None
        if p1:
            st.write("**Caminho lógico reconstruído pelas propriedades Route:** " + " → ".join(
                airports[x].get("iata") or airports[x].get("icao") or x for x in p1
            ))

        native = st.session_state.get("air_native")
        if native:
            degree_rows = (((native.get("degree") or {}).get("payload") or {}).get("resultados") or [])
            src_native = find_native_node_id(degree_rows, selected_id)
            dst_native = find_native_node_id(degree_rows, target["airport_id"])

            if src_native and dst_native:
                st.caption(
                    f"IDs internos NexusDB/CSR: origem={src_native} · destino={dst_native}"
                )
                if st.button("Executar shortestPath no NexusDB / CSR", use_container_width=True):
                    nx_sp = NexusClient(conn["url"], conn["user"], conn["password"], conn["database"])
                    with st.spinner("Executando BFS shortestPath no CSR do NexusDB..."):
                        sp_result = execute_native_shortest_path(nx_sp, src_native, dst_native)
                    st.session_state["air_shortest_native"] = sp_result

                sp_result = st.session_state.get("air_shortest_native")
                if sp_result:
                    s1, s2, s3 = st.columns(3)
                    payload = sp_result.get("payload") or {}
                    s1.metric("Tempo NexusDB", format_ms(sp_result.get("elapsed_ms")))
                    s2.metric("Encontrado", "Sim" if payload.get("found") else "Não")
                    s3.metric("Saltos", payload.get("length", "—"))
                    st.code(sp_result.get("query", ""), language="cypher")

                    if sp_result.get("error"):
                        st.warning(sp_result["error"])
                    else:
                        labels = native_path_labels(payload)
                        if labels:
                            st.success("Shortest path CSR: " + " → ".join(str(x) for x in labels))
                        with st.expander("Resposta nativa do NexusDB"):
                            st.json(payload)
            else:
                st.info(
                    "Execute primeiro Graph Analytics. A V1.5 usa "
                    "`CALL algo.degree() LIMIT 20000` para mapear `airport_id` aos IDs internos "
                    "necessários ao `algo.shortestPath(start_id, end_id)`."
                )
        if simulate:
            st.write("**Após remover o aeroporto de origem:** não existe caminho partindo do nó removido, por definição.")
            st.caption(
                "A análise de resiliência na aba anterior procura caminhos alternativos entre os aeroportos vizinhos "
                "sem utilizar o aeroporto indisponível."
            )
    else:
        st.info("Sem destinos na amostra carregada.")

st.divider()
st.caption(
    "NexusDB AirRoute Resilience V1.6.1 Multi-hop Route Explorer · Graph Analytics + Geospatial + Resilience · "
    "Os dados representam conectividade declarada no dataset OpenFlights, não disponibilidade de voos em tempo real."
)


with tabs[5]:
    st.subheader("Planejador de rotas Airport → Airport")
    st.caption(
        "Escolha qualquer aeroporto de origem e um aeroporto ou país de destino. "
        "1 nível = voo direto; 2 níveis = uma conexão; 3 níveis = duas conexões; "
        "e assim por diante. A busca usa a semântica Route.source_airport_id → "
        "Route.destination_airport_id, evitando que Country/Airline/AircraftType "
        "sejam tratados como escalas aéreas."
    )

    all_candidates = all_airport_candidates(airports, outgoing, incoming)
    if not all_candidates:
        st.warning("Não há aeroportos suficientes carregados para o planejador.")
    else:
        # Default: Paraguay origin if available, otherwise current selected airport.
        origin_default = 0
        for i, a in enumerate(all_candidates):
            if airport_country(a).casefold() == "paraguay":
                origin_default = i
                break

        c1, c2 = st.columns(2)
        with c1:
            origin = st.selectbox(
                "Origem — qualquer país",
                all_candidates,
                index=origin_default,
                format_func=airport_label,
                key="mh_origin",
            )
        with c2:
            destination_mode = st.radio(
                "Destino",
                ["Aeroporto específico", "Qualquer aeroporto de um país"],
                horizontal=True,
                key="mh_dest_mode",
            )

        countries_available = sorted({
            airport_country(a) for a in all_candidates if airport_country(a)
        })

        target_ids = []
        target_label = ""
        if destination_mode == "Aeroporto específico":
            dest_default = 0
            for i, a in enumerate(all_candidates):
                if airport_country(a).casefold() == "portugal":
                    dest_default = i
                    break
            destination = st.selectbox(
                "Aeroporto de destino",
                all_candidates,
                index=dest_default,
                format_func=airport_label,
                key="mh_destination_airport",
            )
            target_ids = [destination["airport_id"]]
            target_label = airport_label(destination)
        else:
            portugal_idx = next(
                (i for i, c in enumerate(countries_available) if c.casefold() == "portugal"), 0
            )
            dest_country = st.selectbox(
                "País de destino",
                countries_available,
                index=portugal_idx,
                key="mh_destination_country",
            )
            target_ids = [
                a["airport_id"] for a in all_candidates
                if airport_country(a) == dest_country
            ]
            target_label = dest_country

        max_legs = st.slider(
            "Máximo de níveis / trechos",
            1, 6, 3, 1,
            help="1 = direto; 2 = uma conexão; 3 = duas conexões.",
        )
        max_paths = st.slider("Máximo de alternativas", 5, 100, 30, 5)

        if st.button("Buscar ligações e conexões", type="primary", use_container_width=True):
            with st.spinner("Explorando a rede de aeroportos..."):
                paths_found = enumerate_airport_paths(
                    routes, origin["airport_id"], target_ids,
                    max_legs=max_legs, max_paths=max_paths
                )
            st.session_state["mh_paths"] = paths_found
            st.session_state["mh_origin_id"] = origin["airport_id"]
            st.session_state["mh_target_label"] = target_label
            st.session_state["mh_max_legs"] = max_legs
            st.session_state["mh_query_signature"] = (
                str(origin["airport_id"]), destination_mode,
                tuple(sorted(str(x) for x in target_ids)),
                int(max_legs), int(max_paths),
            )

        current_signature = (
            str(origin["airport_id"]), destination_mode,
            tuple(sorted(str(x) for x in target_ids)),
            int(max_legs), int(max_paths),
        )
        stored_signature = st.session_state.get("mh_query_signature")
        paths_found = st.session_state.get("mh_paths", []) if stored_signature == current_signature else []

        if stored_signature is not None and stored_signature != current_signature:
            st.info(
                "Origem, destino ou profundidade foram alterados. "
                "Clique em **Buscar ligações e conexões** para atualizar os caminhos e o mapa."
            )

        if paths_found:
            direct = [x for x in paths_found if len(x["airports"]) - 1 == 1]
            connection = [x for x in paths_found if len(x["airports"]) - 1 > 1]
            p1, p2, p3 = st.columns(3)
            p1.metric("Alternativas encontradas", len(paths_found))
            p2.metric("Voos diretos", len(direct))
            p3.metric("Com conexão", len(connection))

            display_rows = []
            for i, item in enumerate(paths_found, 1):
                path = item["airports"]
                legs = len(path) - 1
                dist = path_distance_km(path, airports)
                countries = path_country_sequence(path, airports)
                operators = []
                for leg in item["legs"]:
                    operators.extend(leg["operators"])
                display_rows.append({
                    "#": i,
                    "Níveis/trechos": legs,
                    "Conexões": max(0, legs - 1),
                    "Tipo": "Direto" if legs == 1 else f"{legs-1} conexão(ões)",
                    "Caminho": friendly_path(path, airports),
                    "Países": " → ".join(countries),
                    "Companhias/códigos": ", ".join(sorted(set(operators))) or "—",
                    "Distância aprox. km": round(dist, 0) if dist is not None else None,
                })

            df_paths = pd.DataFrame(display_rows).sort_values(
                ["Níveis/trechos", "Distância aprox. km"], na_position="last"
            )
            st.dataframe(df_paths, hide_index=True, use_container_width=True)

            selected_option = st.selectbox(
                "Visualizar alternativa",
                list(range(len(paths_found))),
                format_func=lambda i: f"#{i+1} — {friendly_path(paths_found[i]['airports'], airports)}",
                key="mh_selected_path",
            )
            chosen = paths_found[selected_option]

            show_all_paths = st.checkbox(
                "Sobrepor todas as alternativas no mapa",
                value=False,
                help="Desmarcado mostra somente o itinerário selecionado.",
                key="mh_show_all_paths",
            )
            selected_countries = path_country_sequence(chosen["airports"], airports)
            st.markdown(
                f"**Itinerário exibido:** {friendly_path(chosen['airports'], airports)}  \n"
                f"**Países atravessados:** {' → '.join(selected_countries) or '—'}"
            )

            deck = build_route_explorer_map(
                paths_found, airports, selected_option, show_all=show_all_paths
            )
            if deck:
                st.pydeck_chart(deck, use_container_width=True)

            st.caption(
                "Verde = alternativa selecionada; azul translúcido = outras alternativas."
                if show_all_paths else
                "O mapa mostra somente os trechos da alternativa selecionada."
            )

            st.markdown("#### Detalhamento dos trechos")
            leg_rows = []
            for n, leg in enumerate(chosen["legs"], 1):
                sa, da = airports.get(leg["source"], {}), airports.get(leg["destination"], {})
                leg_rows.append({
                    "Trecho": n,
                    "Origem": airport_label(sa),
                    "País origem": airport_country(sa),
                    "Destino": airport_label(da),
                    "País destino": airport_country(da),
                    "Rotas declaradas": len(leg["routes"]),
                    "Operadores/códigos": ", ".join(leg["operators"]) or "—",
                })
            st.dataframe(pd.DataFrame(leg_rows), hide_index=True, use_container_width=True)

            # Native CSR shortest path for exact airport destination only.
            native = st.session_state.get("air_native")
            if destination_mode == "Aeroporto específico" and native:
                degree_rows = (((native.get("degree") or {}).get("payload") or {}).get("resultados") or [])
                src_id = find_native_node_id(degree_rows, origin["airport_id"])
                dst_id = find_native_node_id(degree_rows, destination["airport_id"])
                if src_id and dst_id:
                    st.markdown("#### Comparação com shortestPath nativo do NexusDB / CSR")
                    st.caption(
                        "A busca Airport→Airport acima respeita a semântica de voo. "
                        "O shortestPath CSR abaixo percorre o property graph heterogêneo completo; "
                        "por isso pode atravessar Route, Country, Airline e AircraftType."
                    )
                    if st.button("Executar shortestPath CSR para este par", use_container_width=True):
                        nx_sp = NexusClient(conn["url"], conn["user"], conn["password"], conn["database"])
                        csr = execute_native_shortest_path(nx_sp, src_id, dst_id)
                        st.session_state["mh_csr"] = csr
                    csr = st.session_state.get("mh_csr")
                    if csr:
                        a, b = st.columns(2)
                        a.metric("Tempo CSR", format_ms(csr.get("elapsed_ms")))
                        b.metric("Saltos CSR", (csr.get("payload") or {}).get("length", "—"))
                        st.code(csr.get("query", ""), language="cypher")
                        labels = native_path_labels(csr.get("payload") or {})
                        if labels:
                            st.write("**Caminho CSR:** " + " → ".join(map(str, labels)))
                else:
                    st.info(
                        "Execute Graph Analytics para obter os IDs internos dos aeroportos "
                        "e habilitar a comparação com `CALL algo.shortestPath()`."
                    )
        elif "mh_paths" in st.session_state:
            st.warning(
                f"Nenhum caminho encontrado com até {st.session_state.get('mh_max_legs', max_legs)} "
                "trechos no subconjunto de rotas atualmente carregado. "
                "Aumente os níveis ou verifique se todas as Route foram carregadas."
            )
