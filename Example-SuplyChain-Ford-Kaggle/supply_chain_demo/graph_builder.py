import html
from pyvis.network import Network

STATUS_COLOR = {
    "removed": "#ef4444",
    "blocked": "#dc2626",
    "at_risk": "#f59e0b",
    "operational": "#22c55e",
    "normal": "#64748b",
}
SHAPES = {
    "Supplier": "box",
    "Product": "dot",
    "Order": "diamond",
    "Customer": "ellipse",
    "Location": "triangle",
    "ShippingMode": "hexagon",
}


def make_html(nodes, edges, result=None, focus_only=True):
    result = result or {
        "removed": set(),
        "blocked": set(),
        "at_risk": set(),
        "operational": set(),
    }
    important = (
        set(result.get("removed", set()))
        | set(result.get("blocked", set()))
        | set(result.get("at_risk", set()))
    )

    if focus_only and important:
        # Duas expansões dão contexto suficiente sem desenhar todo o banco.
        for _ in range(2):
            snapshot = set(important)
            for e in edges:
                s, t = str(e["source"]), str(e["target"])
                if s in snapshot or t in snapshot:
                    important.update([s, t])
    else:
        important = {str(n["id"]) for n in nodes}

    net = Network(
        height="720px",
        width="100%",
        bgcolor="#0b1220",
        font_color="#e5e7eb",
        directed=True,
    )
    net.barnes_hut(
        gravity=-6500,
        central_gravity=0.22,
        spring_length=165,
        spring_strength=0.025,
    )

    for n in nodes:
        nid = str(n["id"])
        if nid not in important:
            continue

        status = "normal"
        for key in ("removed", "blocked", "at_risk", "operational"):
            if nid in result.get(key, set()):
                status = key
                break

        props = n.get("properties", {})
        label = (
            props.get("name")
            or props.get("car_model")
            or props.get("product_id")
            or props.get("order_id")
            or f"{n.get('label')} {nid}"
        )

        # Tooltip em texto simples: evita mostrar <b>/<br> literalmente.
        title_lines = [str(n.get("label", "Node"))]
        title_lines += [
            f"{k}: {v}"
            for k, v in list(props.items())[:12]
            if v not in (None, "")
        ]
        title = "\n".join(title_lines)

        net.add_node(
            nid,
            label=str(label),
            title=title,
            color=STATUS_COLOR[status],
            shape=SHAPES.get(n.get("label"), "dot"),
        )

    for e in edges:
        s, t = str(e["source"]), str(e["target"])
        if s in important and t in important:
            net.add_edge(
                s,
                t,
                label=e.get("type", ""),
                title=e.get("type", ""),
                arrows="to",
            )

    return net.generate_html()
