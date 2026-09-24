from collections import defaultdict, deque


def _num(value):
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def _indexes(nodes, edges):
    by_id = {str(n["id"]): n for n in nodes}
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for e in edges:
        s, t = str(e["source"]), str(e["target"])
        outgoing[s].append(e)
        incoming[t].append(e)
    return by_id, outgoing, incoming


def _sources(incoming, target, rel_type):
    return {
        str(e["source"])
        for e in incoming.get(str(target), [])
        if e.get("type") == rel_type
    }


def _targets(outgoing, source, rel_type):
    return {
        str(e["target"])
        for e in outgoing.get(str(source), [])
        if e.get("type") == rel_type
    }


def analyze_supply_risk(nodes, edges, selected_id):
    """
    Analisa risco de indisponibilidade de Supplier ou Product.

    IMPORTANTE:
    SUPPLIES é tratado como evidência de redundância de fornecedor observada
    no dataset. Isso não é uma BOM industrial nem prova capacidade real de
    substituição. "Alternativo" significa apenas que outro Supplier também
    aparece ligado ao mesmo Product no grafo carregado.
    """
    by_id, outgoing, incoming = _indexes(nodes, edges)
    selected_id = str(selected_id)
    selected = by_id.get(selected_id)
    if not selected:
        raise ValueError(f"Nó não encontrado: {selected_id}")

    kind = selected.get("label")
    removed = {selected_id}
    blocked_products = set()
    at_risk_products = set()
    alternative_suppliers = defaultdict(set)

    if kind == "Supplier":
        products = _targets(outgoing, selected_id, "SUPPLIES")
        for pid in products:
            suppliers = _sources(incoming, pid, "SUPPLIES")
            alternatives = suppliers - {selected_id}
            if alternatives:
                at_risk_products.add(pid)
                alternative_suppliers[pid] = alternatives
            else:
                blocked_products.add(pid)

    elif kind == "Product":
        products = {selected_id}
        blocked_products.add(selected_id)
        suppliers = _sources(incoming, selected_id, "SUPPLIES")
        alternative_suppliers[selected_id] = suppliers
    else:
        products = set()

    # Pedidos ligados a produtos bloqueados ficam expostos.
    affected_orders = set()
    for pid in blocked_products:
        affected_orders |= _sources(incoming, pid, "CONTAINS")

    # Pedidos ligados a produtos "em risco" são exposição secundária.
    at_risk_orders = set()
    for pid in at_risk_products:
        at_risk_orders |= _sources(incoming, pid, "CONTAINS")
    at_risk_orders -= affected_orders

    # Clientes que fizeram pedidos expostos.
    affected_customers = set()
    at_risk_customers = set()
    for oid in affected_orders:
        affected_customers |= _sources(incoming, oid, "PLACED")
    for oid in at_risk_orders:
        at_risk_customers |= _sources(incoming, oid, "PLACED")
    at_risk_customers -= affected_customers

    # Destinos/modos associados aos pedidos são contexto operacional.
    affected_locations = set()
    affected_shipping = set()
    for oid in affected_orders:
        affected_locations |= _targets(outgoing, oid, "DELIVERED_TO")
        affected_shipping |= _targets(outgoing, oid, "SHIPPED_VIA")

    revenue_exposed = 0.0
    quantity_exposed = 0.0
    for oid in affected_orders:
        props = by_id.get(oid, {}).get("properties", {})
        revenue_exposed += _num(props.get("sales"))
        quantity_exposed += _num(props.get("quantity"))

    # Dependência exclusiva dos produtos diretamente analisados.
    product_scope = blocked_products | at_risk_products
    exclusive = 0
    redundancy_values = []
    for pid in product_scope:
        supplier_count = len(_sources(incoming, pid, "SUPPLIES"))
        if supplier_count <= 1:
            exclusive += 1
        redundancy_values.append(max(0, supplier_count - 1))

    exclusive_ratio = exclusive / len(product_scope) if product_scope else 0.0
    avg_alternatives = (
        sum(redundancy_values) / len(redundancy_values)
        if redundancy_values else 0.0
    )

    # Centralidade de grau simples do elemento selecionado.
    max_degree = max(
        [len(outgoing[nid]) + len(incoming[nid]) for nid in by_id] or [1]
    )
    selected_degree = len(outgoing[selected_id]) + len(incoming[selected_id])
    degree_centrality = selected_degree / max_degree if max_degree else 0.0

    # Componentes normalizados do score. Os denominadores são deliberadamente
    # transparentes e configuráveis; servem para demonstração, não como modelo
    # universal de risco.
    dependency_component = min(1.0, exclusive_ratio)
    order_component = min(1.0, len(affected_orders) / 25.0)
    revenue_component = min(1.0, revenue_exposed / 250000.0)
    customer_component = min(1.0, len(affected_customers) / 25.0)
    graph_component = min(1.0, degree_centrality)

    score = 100.0 * (
        0.30 * dependency_component
        + 0.25 * order_component
        + 0.20 * revenue_component
        + 0.15 * customer_component
        + 0.10 * graph_component
    )

    if score >= 70:
        risk_level = "CRÍTICO"
    elif score >= 50:
        risk_level = "ALTO"
    elif score >= 25:
        risk_level = "MODERADO"
    else:
        risk_level = "BAIXO"

    resilience = "BAIXA" if exclusive_ratio >= 0.67 else (
        "MÉDIA" if exclusive_ratio >= 0.34 else "ALTA"
    )

    blocked = blocked_products | affected_orders | affected_customers
    at_risk = at_risk_products | at_risk_orders | at_risk_customers
    operational = set(by_id) - removed - blocked - at_risk

    # Caminhos legíveis para a aba de impacto.
    paths = []
    if kind == "Supplier":
        for pid in sorted(product_scope):
            p_status = "BLOQUEADO" if pid in blocked_products else "EM RISCO"
            orders = _sources(incoming, pid, "CONTAINS")
            if not orders:
                paths.append([selected_id, pid])
            for oid in sorted(orders):
                customers = _sources(incoming, oid, "PLACED")
                if customers:
                    for cid in sorted(customers):
                        paths.append([selected_id, pid, oid, cid])
                else:
                    paths.append([selected_id, pid, oid])
    elif kind == "Product":
        for oid in sorted(affected_orders):
            customers = _sources(incoming, oid, "PLACED")
            if customers:
                for cid in sorted(customers):
                    paths.append([selected_id, oid, cid])
            else:
                paths.append([selected_id, oid])

    return {
        "selected": selected_id,
        "kind": kind,
        "removed": removed,
        "blocked": blocked,
        "at_risk": at_risk,
        "operational": operational,
        "blocked_products": blocked_products,
        "at_risk_products": at_risk_products,
        "affected_orders": affected_orders,
        "at_risk_orders": at_risk_orders,
        "affected_customers": affected_customers,
        "at_risk_customers": at_risk_customers,
        "affected_locations": affected_locations,
        "affected_shipping": affected_shipping,
        "alternative_suppliers": {
            k: sorted(v) for k, v in alternative_suppliers.items()
        },
        "revenue_exposed": revenue_exposed,
        "quantity_exposed": quantity_exposed,
        "exclusive_ratio": exclusive_ratio,
        "avg_alternatives": avg_alternatives,
        "selected_degree": selected_degree,
        "degree_centrality": degree_centrality,
        "risk_score": round(score, 1),
        "risk_level": risk_level,
        "resilience": resilience,
        "components": {
            "Dependência": dependency_component,
            "Pedidos": order_component,
            "Receita": revenue_component,
            "Clientes": customer_component,
            "Centralidade": graph_component,
        },
        "paths": paths[:250],
    }
