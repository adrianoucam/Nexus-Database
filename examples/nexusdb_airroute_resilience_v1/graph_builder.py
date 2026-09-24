from pyvis.network import Network

SHAPES = {
    "Airport": "dot",
    "Route": "diamond",
    "Airline": "box",
    "Country": "triangle",
}


def make_network_html(airports, routes, airlines, countries,
                      selected_id=None, focus_only=True, removed_id=None):
    net = Network(
        height="735px", width="100%", bgcolor="#0b1220",
        font_color="#e5e7eb", directed=True
    )
    net.barnes_hut(
        gravity=-5500, central_gravity=0.22,
        spring_length=145, spring_strength=0.025
    )

    route_ids = set()
    airport_ids = set()
    airline_ids = set()
    country_names = set()

    if focus_only and selected_id:
        airport_ids.add(selected_id)
        for rk, r in routes.items():
            if r.get("source") == selected_id or r.get("destination") == selected_id:
                route_ids.add(rk)
                airport_ids.update([r.get("source"), r.get("destination")])
                if r.get("operator_id"):
                    airline_ids.add(r["operator_id"])
        for aid in airport_ids:
            if aid in airports and airports[aid].get("country"):
                country_names.add(airports[aid]["country"])
    else:
        # Proteção visual: não tente desenhar dezenas de milhares de nós.
        ranked = sorted(
            airports,
            key=lambda aid: sum(
                1 for r in routes.values()
                if r.get("source") == aid or r.get("destination") == aid
            ),
            reverse=True
        )[:150]
        airport_ids.update(ranked)
        for rk, r in routes.items():
            if r.get("source") in airport_ids and r.get("destination") in airport_ids:
                route_ids.add(rk)
                if r.get("operator_id"):
                    airline_ids.add(r["operator_id"])
        for aid in airport_ids:
            if airports.get(aid, {}).get("country"):
                country_names.add(airports[aid]["country"])

    for aid in airport_ids:
        a = airports.get(aid)
        if not a:
            continue
        code = a.get("iata") or a.get("icao") or aid
        title = "\n".join(
            f"{k}: {v}" for k, v in a.items() if v not in (None, "")
        )
        color = "#ef4444" if aid == removed_id else (
            "#38bdf8" if aid == selected_id else "#60a5fa"
        )
        net.add_node(
            "Airport:"+aid, label=str(code), title=title,
            shape=SHAPES["Airport"], color=color, size=24 if aid == selected_id else 15
        )

    for rk in route_ids:
        r = routes[rk]
        known = bool(r.get("operator_id") and r.get("operator_id") in airlines)
        net.add_node(
            "Route:"+rk, label="Route",
            title=f"Route: {rk}\nOperator identified: {known}\nEquipment: {r.get('equipment','')}",
            shape=SHAPES["Route"],
            color="#22c55e" if known else "#f59e0b",
            size=10
        )
        s, d = r.get("source"), r.get("destination")
        if s in airport_ids:
            net.add_edge("Airport:"+s, "Route:"+rk, label="DEPARTURE", arrows="to")
        if d in airport_ids:
            net.add_edge("Route:"+rk, "Airport:"+d, label="ARRIVAL", arrows="to")

        alid = r.get("operator_id")
        if alid in airline_ids and alid in airlines:
            al = airlines[alid]
            net.add_node(
                "Airline:"+alid,
                label=str(al.get("iata") or al.get("name") or alid),
                title="\n".join(f"{k}: {v}" for k, v in al.items() if v not in (None, "")),
                shape=SHAPES["Airline"], color="#a78bfa"
            )
            net.add_edge("Airline:"+alid, "Route:"+rk, label="OPERATES", arrows="to")

    # Países são conectados visualmente a aeroportos usando a propriedade country.
    # A relação original no banco é Airport-[:LOCATED_IN]->Country.
    for cname in country_names:
        net.add_node(
            "Country:"+cname, label=str(cname), title=f"Country: {cname}",
            shape=SHAPES["Country"], color="#f472b6"
        )
    for aid in airport_ids:
        cname = airports.get(aid, {}).get("country")
        if cname in country_names:
            net.add_edge("Airport:"+aid, "Country:"+cname, label="LOCATED_IN", arrows="to")

    return net.generate_html()
