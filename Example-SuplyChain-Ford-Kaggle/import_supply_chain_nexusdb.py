#!/usr/bin/env python3
"""
Importador Supply Chain Kaggle -> NexusDB.

Cria um database separado (SUPPLY_CHAIN_KAGGLE) e transforma o CSV tabular
em property graph:

(Supplier)-[:SUPPLIES]->(Product)
(Customer)-[:PLACED]->(Order)
(Order)-[:CONTAINS]->(Product)
(Order)-[:SHIPPED_VIA]->(ShippingMode)
(Order)-[:DELIVERED_TO]->(Location)

Uso:
  python import_supply_chain_nexusdb.py --csv supply_chain.csv --password SUA_SENHA

Observação de segurança:
  CreditCard não é importado. CreditCardType é mantido no Order.
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
from typing import Any

DEFAULT_DB = "SUPPLY_CHAIN_KAGGLE"


@dataclass
class NexusClient:
    base_url: str
    user: str
    password: str
    database: str
    timeout: float = 180

    def _post(self, path: str, payload: dict[str, Any], database: str | None = None) -> dict[str, Any]:
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
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                out = json.loads(response.read().decode("utf-8"))
                if out.get("status") in ("error", "partial_error") or out.get("errors"):
                    raise RuntimeError(f"Falha em {path}: {out}")
                return out
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
        except (OSError, TimeoutError) as exc:
            raise RuntimeError(f"Conexão interrompida em {path}; a escrita pode ter sido parcial. Não repita em um banco preenchido: {exc}") from exc

    def create_database(self) -> None:
        out = self._post("/db/admin/database/create", {"database": self.database}, database="system")
        if out.get("status") != "success":
            raise RuntimeError(f"Falha criando database: {out}")

    def cypher(self, query: str) -> dict[str, Any]:
        out = self._post("/db/data/cypher", {"statements": [{"query": query}]})
        if out.get("errors"):
            raise RuntimeError(f"Cypher falhou: {out['errors']}\nQuery: {query}")
        return out

    def create_node(self, label: str, props: dict[str, Any]) -> int:
        # O CREATE do NexusDB aceita um objeto JSON como mapa de propriedades.
        q = f"CREATE (:{label} {json.dumps(props, ensure_ascii=False, separators=(',', ':'))})"
        out = self.cypher(q)
        # O endpoint Cypher atual retorna a mensagem de criação.
        text = json.dumps(out, ensure_ascii=False)
        match = re.search(r"id=(\d+)", text)
        if not match:
            raise RuntimeError(f"NexusDB não retornou id do nó criado: {out}")
        return int(match.group(1))

    def create_relationship(self, source: int, target: int, rel_type: str) -> None:
        # Usa o endpoint que efetivamente grava e replica as arestas.
        out = self._post("/db/data/relationship/bulk", {
            "rows": [{"from": source, "to": target, "type": rel_type, "properties": {}}]
        })
        if out.get("processados") != 1:
            raise RuntimeError(f"Relacionamento não confirmado: {out}")

    def create_index(self, label: str, field: str) -> None:
        self.cypher(f"CREATE INDEX ON :{label}({field})")


class BatchWriter:
    def __init__(self, client: NexusClient, size: int):
        self.client, self.size = client, size
        self.ids: dict[int, int] = {}
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[tuple[int, int, str]] = []
        self.next_key = 0

    def node(self, label: str, properties: dict[str, Any]) -> int:
        key = self.next_key
        self.next_key += 1
        self.nodes.append({"key": key, "label": label, "properties": properties})
        return key

    def flush(self) -> None:
        for start in range(0, len(self.nodes), self.size):
            batch = self.nodes[start:start + self.size]
            print(f"Gravando lote de {len(batch)} nós...", flush=True)
            out = self.client._post("/db/data/node/bulk", {"rows": batch})
            results = out.get("resultados", [])
            expected = {row["key"] for row in batch}
            if out.get("processados") != len(batch) or len(results) != len(batch) or {r.get("key") for r in results} != expected:
                raise RuntimeError("Lote de nós incompleto; importação interrompida")
            for row in results:
                if not isinstance(row.get("id"), int):
                    raise RuntimeError("Resposta de nó sem ID válido")
                self.ids[row["key"]] = row["id"]
        for start in range(0, len(self.edges), self.size):
            batch = self.edges[start:start + self.size]
            print(f"Gravando lote de {len(batch)} relacionamentos...", flush=True)
            rows = [{"from": self.ids[a], "to": self.ids[b], "type": t, "properties": {}} for a, b, t in batch]
            out = self.client._post("/db/data/relationship/bulk", {"rows": rows})
            if out.get("processados") != len(rows):
                raise RuntimeError("Lote de relacionamentos incompleto; importação interrompida")
        self.nodes.clear()
        self.edges.clear()


def s(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def number(row: dict[str, str], key: str, integer: bool = False) -> int | float | None:
    raw = s(row, key)
    if not raw:
        return None
    try:
        return int(float(raw)) if integer else float(raw)
    except ValueError:
        return None


def compact(props: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in props.items() if v not in (None, "")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV completo baixado do Kaggle")
    ap.add_argument("--url", default="http://127.0.0.1:7474")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--database", default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=0, help="0 = importar todo o CSV")
    ap.add_argument("--batch-size", type=int, default=100, help="Operações por requisição (1 a 1000)")
    ap.add_argument("--timeout", type=float, default=180, help="Timeout HTTP em segundos")
    args = ap.parse_args()
    if not 1 <= args.batch_size <= 1000 or args.limit < 0 or args.timeout <= 0:
        ap.error("batch-size deve ser 1..1000, limit >= 0 e timeout > 0")
    started = time.monotonic()
    print(f"Importando para {args.database}; lotes de {args.batch_size}; limite={args.limit or 'todo o CSV'}", flush=True)

    nx = NexusClient(args.url, args.user, args.password, args.database, args.timeout)
    nx.create_database()
    stats = nx.cypher("CALL db.stats()")["resultados"][0]
    if stats["nodes"] or stats["relationships"]:
        raise RuntimeError("O banco já contém dados. Use um banco vazio para evitar duplicações.")
    writer = BatchWriter(nx, args.batch_size)
    processed = 0

    # Cache evita duplicar entidades quando IDs reaparecem no CSV.
    suppliers: dict[str, int] = {}
    products: dict[str, int] = {}
    customers: dict[str, int] = {}
    locations: dict[str, int] = {}
    ship_modes: dict[str, int] = {}
    orders: dict[str, int] = {}
    rels: set[tuple[int, int, str]] = set()

    def node(cache: dict[str, int], key: str, label: str, props: dict[str, Any]) -> int:
        if key in cache:
            return cache[key]
        node_id = writer.node(label, compact(props))
        cache[key] = node_id
        return node_id

    def rel(a: int, b: int, typ: str) -> None:
        signature = (a, b, typ)
        if signature not in rels:
            writer.edges.append(signature)
            rels.add(signature)

    with open(args.csv, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=1):
            if args.limit and i > args.limit:
                break

            supplier_key = s(row, "SupplierID")
            product_key = s(row, "ProductID")
            customer_key = s(row, "CustomerID")
            order_key = s(row, "OrderID")
            location_key = "|".join([s(row, "PostalCode"), s(row, "City"), s(row, "State"), s(row, "Country")])
            ship_key = s(row, "ShipMode") or "UNKNOWN"

            supplier_id = node(suppliers, supplier_key, "Supplier", {
                "supplier_id": supplier_key,
                "name": s(row, "SupplierName"),
                "address": s(row, "SupplierAddress"),
                "contact": s(row, "SupplierContactDetails"),
            })
            product_id = node(products, product_key, "Product", {
                "product_id": product_key,
                "car_maker": s(row, "CarMaker"),
                "car_model": s(row, "CarModel"),
                "color": s(row, "CarColor"),
                "model_year": number(row, "CarModelYear", True),
                "price": number(row, "CarPrice"),
            })
            customer_id = node(customers, customer_key, "Customer", {
                "customer_id": customer_key,
                "name": s(row, "CustomerName"),
                "gender": s(row, "Gender"),
                "job_title": s(row, "JobTitle"),
                "phone": s(row, "PhoneNumber"),
                "email": s(row, "EmailAddress"),
                "address": s(row, "CustomerAddress"),
            })
            location_id = node(locations, location_key, "Location", {
                "postal_code": s(row, "PostalCode"),
                "city": s(row, "City"),
                "state": s(row, "State"),
                "country": s(row, "Country"),
                "country_code": s(row, "CountryCode"),
            })
            shipping_id = node(ship_modes, ship_key, "ShippingMode", {
                "name": ship_key,
                "transport": s(row, "Shipping"),
            })
            order_id = node(orders, order_key, "Order", {
                "order_id": order_key,
                "order_date": s(row, "OrderDate"),
                "ship_date": s(row, "ShipDate"),
                "sales": number(row, "Sales"),
                "quantity": number(row, "Quantity", True),
                "discount": number(row, "Discount"),
                "credit_card_type": s(row, "CreditCardType"),
                "customer_feedback": s(row, "CustomerFeedback"),
            })

            rel(supplier_id, product_id, "SUPPLIES")
            rel(customer_id, order_id, "PLACED")
            rel(order_id, product_id, "CONTAINS")
            rel(order_id, shipping_id, "SHIPPED_VIA")
            rel(order_id, location_id, "DELIVERED_TO")

            processed = i
            if i % args.batch_size == 0:
                writer.flush()
                print(f"{i:,} linhas confirmadas | {time.monotonic()-started:.1f}s", flush=True)

    writer.flush()
    print(f"{processed} linhas confirmadas. Criando índices...", flush=True)

    # Índices úteis para MATCH/WHERE e futuros planos híbridos.
    for label, field in [
        ("Supplier", "supplier_id"),
        ("Product", "product_id"),
        ("Product", "car_maker"),
        ("Customer", "customer_id"),
        ("Order", "order_id"),
        ("Location", "postal_code"),
        ("Location", "city"),
        ("ShippingMode", "name"),
    ]:
        try:
            nx.create_index(label, field)
        except Exception as exc:
            print(f"[WARN] índice {label}.{field}: {exc}", file=sys.stderr)

    print(json.dumps({
        "database": args.database,
        "suppliers": len(suppliers),
        "products": len(products),
        "customers": len(customers),
        "orders": len(orders),
        "locations": len(locations),
        "shipping_modes": len(ship_modes),
        "relationships": len(rels),
        "rows": processed,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
