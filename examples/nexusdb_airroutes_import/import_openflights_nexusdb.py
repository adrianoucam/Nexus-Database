#!/usr/bin/env python3
"""
OpenFlights .dat -> NexusDB

Modelo:
(Country)<-[:LOCATED_IN]-(Airport)
(Country)<-[:BASED_IN]-(Airline)
(Airport)-[:DEPARTURE]->(Route)-[:ARRIVAL]->(Airport)
(Airline)-[:OPERATES]->(Route)
(Route)-[:USES_AIRCRAFT]->(AircraftType)

O Route é um nó propositalmente: permite simular cancelamento de rota,
indisponibilidade de aeroporto/companhia e explicar os caminhos no grafo.

Usa os endpoints bulk nativos do NexusDB para reduzir o número de requisições.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NULL = r"\N"
DEFAULT_DB = "OPENFLIGHTS_GRAPH"


def clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return None if not v or v == NULL else v


def num(v: str | None, integer: bool = False):
    v = clean(v)
    if v is None:
        return None
    try:
        return int(float(v)) if integer else float(v)
    except ValueError:
        return None


def compact(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None and v != ""}


@dataclass
class NexusClient:
    base_url: str
    user: str
    password: str
    database: str

    def _post(self, path: str, payload: dict[str, Any],
              database: str | None = None) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-User": self.user,
                "X-Pass": self.password,
                "X-Database": database or self.database,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                raw = response.read().decode("utf-8", "replace")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falha conectando a {self.base_url}: {exc}") from exc

    def authenticate_once(self):
        # Uma senha errada não dispara vários lotes.
        out = self._post(
            "/db/data/cypher",
            {"statements": [{"query": "CALL DB.STATS()"}]},
        )
        if out.get("status") in ("error", "failed") or out.get("errors"):
            raise RuntimeError(f"Pré-autenticação falhou: {out}")
        return out

    def create_database(self):
        out = self._post(
            "/db/admin/database/create",
            {"database": self.database},
            database="system",
        )
        # Algumas versões podem responder que já existe; nesse caso o usuário
        # deve usar --reuse explicitamente para evitar duplicação acidental.
        return out

    def bulk_nodes(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        if not rows:
            return {}
        out = self._post("/db/data/node/bulk", {"rows": rows})
        if out.get("status") not in ("success", "partial_error"):
            raise RuntimeError(f"Falha no bulk de nós: {out}")
        if out.get("errors"):
            raise RuntimeError(f"Bulk de nós parcialmente inválido: {out['errors'][:5]}")

        mapping: dict[str, int] = {}
        for item in out.get("resultados", []):
            key = str(item.get("key"))
            node_id = item.get("id")
            if node_id is None:
                # Compatibilidade defensiva com respostas textuais antigas.
                m = re.search(r"id=(\d+)", json.dumps(item, ensure_ascii=False))
                if m:
                    node_id = int(m.group(1))
            if node_id is None:
                raise RuntimeError(f"Resposta bulk sem id: {item}")
            mapping[key] = int(node_id)
        return mapping

    def bulk_relationships(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        out = self._post("/db/data/relationship/bulk", {"rows": rows})
        if out.get("status") not in ("success", "partial_error"):
            raise RuntimeError(f"Falha no bulk de relações: {out}")
        if out.get("errors"):
            raise RuntimeError(
                f"Bulk de relações parcialmente inválido: {out['errors'][:5]}"
            )
        return int(out.get("processados", len(out.get("resultados", []))))

    def cypher(self, query: str):
        out = self._post(
            "/db/data/cypher",
            {"statements": [{"query": query}]},
        )
        if out.get("errors"):
            raise RuntimeError(f"Cypher: {out['errors']}")
        return out


def read_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        return list(csv.reader(fh))


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def load_sources(folder: Path, use_extended: bool):
    airport_name = "airports-extended.dat" if use_extended else "airports.dat"
    required = [
        "airlines.dat", airport_name, "countries.dat",
        "planes.dat", "routes.dat",
    ]
    missing = [name for name in required if not (folder / name).exists()]
    if missing:
        raise FileNotFoundError("Arquivos ausentes: " + ", ".join(missing))

    return {
        "airlines": read_rows(folder / "airlines.dat"),
        "airports": read_rows(folder / airport_name),
        "countries": read_rows(folder / "countries.dat"),
        "planes": read_rows(folder / "planes.dat"),
        "routes": read_rows(folder / "routes.dat"),
        "airport_file": airport_name,
    }


def prepare(data, route_limit=0):
    # ---------- Countries ----------
    countries = {}
    country_name_to_key = {}
    for i, r in enumerate(data["countries"]):
        if len(r) < 3:
            continue
        name, iso, dafif = map(clean, r[:3])
        if not name:
            continue
        key = iso or f"NAME:{name}"
        countries[key] = compact({
            "name": name, "iso_code": iso, "dafif_code": dafif
        })
        country_name_to_key[name.casefold()] = key

    # Países presentes em Airport/Airline mas ausentes de countries.dat
    def ensure_country(name):
        name = clean(name)
        if not name:
            return None
        k = country_name_to_key.get(name.casefold())
        if k:
            return k
        k = f"NAME:{name}"
        countries.setdefault(k, {"name": name})
        country_name_to_key[name.casefold()] = k
        return k

    # ---------- Airports ----------
    airports = {}
    airport_iata = {}
    airport_icao = {}
    for r in data["airports"]:
        if len(r) < 14:
            continue
        aid = clean(r[0])
        if not aid:
            continue
        props = compact({
            "airport_id": aid,
            "name": clean(r[1]),
            "city": clean(r[2]),
            "country": clean(r[3]),
            "iata": clean(r[4]),
            "icao": clean(r[5]),
            "latitude": num(r[6]),
            "longitude": num(r[7]),
            "altitude_ft": num(r[8], True),
            "timezone_offset": num(r[9]),
            "dst": clean(r[10]),
            "tz_database": clean(r[11]),
            "type": clean(r[12]),
            "source": clean(r[13]),
        })
        airports[aid] = props
        if props.get("iata"):
            airport_iata[props["iata"]] = aid
        if props.get("icao"):
            airport_icao[props["icao"]] = aid
        ensure_country(props.get("country"))

    # ---------- Airlines ----------
    airlines = {}
    airline_iata = {}
    airline_icao = {}
    for r in data["airlines"]:
        if len(r) < 8:
            continue
        alid = clean(r[0])
        if not alid:
            continue
        props = compact({
            "airline_id": alid,
            "name": clean(r[1]),
            "alias": clean(r[2]),
            "iata": clean(r[3]),
            "icao": clean(r[4]),
            "callsign": clean(r[5]),
            "country": clean(r[6]),
            "active": clean(r[7]),
        })
        airlines[alid] = props
        if props.get("iata") and props["iata"] != "-":
            airline_iata[props["iata"]] = alid
        if props.get("icao"):
            airline_icao[props["icao"]] = alid
        ensure_country(props.get("country"))

    # ---------- Aircraft types ----------
    aircraft = {}
    for r in data["planes"]:
        if len(r) < 3:
            continue
        name, iata, icao = map(clean, r[:3])
        key = iata or icao or (f"NAME:{name}" if name else None)
        if key:
            aircraft[key] = compact({
                "name": name, "iata_code": iata, "icao_code": icao
            })

    # ---------- Routes ----------
    routes = []
    unresolved_airport = 0
    unresolved_airline = 0
    equipment_unknown = set()

    def resolve_airport(code, ident):
        ident = clean(ident)
        code = clean(code)
        if ident and ident in airports:
            return ident
        if code and code in airport_iata:
            return airport_iata[code]
        if code and code in airport_icao:
            return airport_icao[code]
        return None

    for idx, r in enumerate(data["routes"], 1):
        if route_limit and len(routes) >= route_limit:
            break
        if len(r) < 9:
            continue

        airline_code, airline_id = clean(r[0]), clean(r[1])
        src = resolve_airport(r[2], r[3])
        dst = resolve_airport(r[4], r[5])
        if not src or not dst:
            unresolved_airport += 1
            continue

        alid = airline_id if airline_id in airlines else None
        if not alid and airline_code:
            alid = airline_iata.get(airline_code) or airline_icao.get(airline_code)
        if not alid:
            unresolved_airline += 1

        equipment = (clean(r[8]) or "").split()
        for eq in equipment:
            if eq not in aircraft:
                # Mantemos o código mesmo sem descrição no planes.dat.
                aircraft[eq] = {"iata_code": eq, "name": f"Equipment {eq}"}
                equipment_unknown.add(eq)

        route_key = f"route:{idx}:{airline_code or 'NA'}:{src}:{dst}"
        routes.append({
            "key": route_key,
            "airline_id": alid,
            "airline_code": airline_code,
            "source_airport_id": src,
            "destination_airport_id": dst,
            "codeshare": clean(r[6]),
            "stops": num(r[7], True) or 0,
            "equipment": equipment,
        })

    return {
        "countries": countries,
        "airports": airports,
        "airlines": airlines,
        "aircraft": aircraft,
        "routes": routes,
        "country_name_to_key": country_name_to_key,
        "unresolved_airport_routes": unresolved_airport,
        "unresolved_airline_routes": unresolved_airline,
        "equipment_created_from_routes": len(equipment_unknown),
    }


def main():
    ap = argparse.ArgumentParser(
        description="Importa OpenFlights para NexusDB como property graph."
    )
    ap.add_argument("--folder", required=True,
                    help="Pasta contendo os arquivos .dat")
    ap.add_argument("--url", default="http://127.0.0.1:7474")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--database", default=DEFAULT_DB)
    ap.add_argument("--batch-size", type=int, default=500)
    ap.add_argument("--route-limit", type=int, default=0,
                    help="0=todas; útil para teste, ex.: 1000")
    ap.add_argument("--use-basic-airports", action="store_true",
                    help="Usa airports.dat; padrão é airports-extended.dat")
    ap.add_argument("--dry-run", action="store_true",
                    help="Valida e mostra estatísticas sem gravar no NexusDB")
    ap.add_argument("--reuse", action="store_true",
                    help="Não tenta criar o database (cuidado com duplicação)")
    args = ap.parse_args()

    started = time.time()
    data = load_sources(Path(args.folder), not args.use_basic_airports)
    model = prepare(data, args.route_limit)

    summary = {
        "airport_file": data["airport_file"],
        "countries": len(model["countries"]),
        "airports": len(model["airports"]),
        "airlines": len(model["airlines"]),
        "aircraft_types": len(model["aircraft"]),
        "routes_valid": len(model["routes"]),
        "routes_unresolved_airports": model["unresolved_airport_routes"],
        "routes_without_resolved_airline": model["unresolved_airline_routes"],
        "equipment_codes_added_from_routes":
            model["equipment_created_from_routes"],
    }
    print("Pré-validação:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        return 0

    nx = NexusClient(args.url, args.user, args.password, args.database)

    # IMPORTANTE: só uma tentativa de autenticação antes de qualquer lote.
    nx = NexusClient(args.url, args.user, args.password, args.database)

    # ------------------------------------------------------------
    # 1. Criar o database antes de tentar executar CALL DB.STATS()
    # ------------------------------------------------------------
    if not args.reuse:
        print(f"Criando database '{args.database}'...")

        created = nx.create_database()

        if created.get("status") != "success":
            raise RuntimeError(
                "Não foi possível criar o database. "
                "Se ele já existe e você realmente quer reutilizá-lo, "
                "execute com --reuse.\n"
                + json.dumps(created, ensure_ascii=False)
            )

        print(f"Database '{args.database}' criado com sucesso.")

    # ------------------------------------------------------------
    # 2. Agora validar autenticação + acesso ao database
    # ------------------------------------------------------------
    print(f"Validando acesso ao database '{args.database}'...")

    nx.authenticate_once()

    print("Autenticação e acesso ao database confirmados.")

    idmap: dict[str, int] = {}

    def insert_entities(label, entities):
        rows = [
            {"key": f"{label}:{key}", "label": label, "properties": props}
            for key, props in entities.items()
        ]
        total = 0
        for batch in chunks(rows, args.batch_size):
            ids = nx.bulk_nodes(batch)
            idmap.update(ids)
            total += len(batch)
            print(f"Nós {label}: {total}/{len(rows)}")
        return total

    insert_entities("Country", model["countries"])
    insert_entities("Airport", model["airports"])
    insert_entities("Airline", model["airlines"])
    insert_entities("AircraftType", model["aircraft"])

    # Route precisa ser inserido depois para obter seus IDs.
    route_entities = {
        r["key"]: compact({
            "route_key": r["key"],
            "airline_code": r["airline_code"],
            "source_airport_id": r["source_airport_id"],
            "destination_airport_id": r["destination_airport_id"],
            "codeshare": r["codeshare"],
            "stops": r["stops"],
            "equipment": " ".join(r["equipment"]),
        })
        for r in model["routes"]
    }
    insert_entities("Route", route_entities)

    rel_rows = []
    rel_seen = set()

    def add_rel(a_key, b_key, typ, props=None):
        a = idmap.get(a_key)
        b = idmap.get(b_key)
        if a is None or b is None:
            return
        signature = (a, b, typ)
        if signature in rel_seen:
            return
        rel_seen.add(signature)
        rel_rows.append({
            "key": f"{typ}:{a}:{b}",
            "from": a,
            "to": b,
            "type": typ,
            "properties": props or {},
        })

    # Airport -> Country
    for aid, p in model["airports"].items():
        cname = p.get("country")
        if cname:
            ckey = model["country_name_to_key"].get(cname.casefold())
            if ckey:
                add_rel(f"Airport:{aid}", f"Country:{ckey}", "LOCATED_IN")

    # Airline -> Country
    for alid, p in model["airlines"].items():
        cname = p.get("country")
        if cname:
            ckey = model["country_name_to_key"].get(cname.casefold())
            if ckey:
                add_rel(f"Airline:{alid}", f"Country:{ckey}", "BASED_IN")

    # Route graph
    for r in model["routes"]:
        rk = f"Route:{r['key']}"
        add_rel(f"Airport:{r['source_airport_id']}", rk, "DEPARTURE")
        add_rel(rk, f"Airport:{r['destination_airport_id']}", "ARRIVAL")

        if r["airline_id"]:
            add_rel(f"Airline:{r['airline_id']}", rk, "OPERATES")

        for eq in r["equipment"]:
            add_rel(rk, f"AircraftType:{eq}", "USES_AIRCRAFT")

    rel_total = 0
    for batch in chunks(rel_rows, args.batch_size):
        rel_total += nx.bulk_relationships(batch)
        print(f"Relações: {rel_total}/{len(rel_rows)}")

    # Índices para a futura aplicação Streamlit.
    indexes = [
        ("Airport", "airport_id"), ("Airport", "iata"),
        ("Airport", "icao"), ("Airport", "country"),
        ("Airline", "airline_id"), ("Airline", "iata"),
        ("Airline", "active"), ("Route", "route_key"),
        ("Country", "iso_code"), ("AircraftType", "iata_code"),
    ]
    for label, field in indexes:
        try:
            nx.cypher(f"CREATE INDEX ON :{label}({field})")
        except Exception as exc:
            print(f"[WARN] índice {label}.{field}: {exc}", file=sys.stderr)

    elapsed = time.time() - started
    final = {
        **summary,
        "database": args.database,
        "nodes": len(idmap),
        "relationships": rel_total,
        "elapsed_seconds": round(elapsed, 2),
    }
    print("\nIMPORTAÇÃO CONCLUÍDA")
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
