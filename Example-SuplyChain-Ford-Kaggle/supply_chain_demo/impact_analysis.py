from collections import defaultdict, deque


def build_indexes(nodes, edges):
    outgoing, incoming = defaultdict(list), defaultdict(list)
    by_id = {str(n['id']): n for n in nodes}
    for e in edges:
        s, t = str(e['source']), str(e['target'])
        outgoing[s].append(e); incoming[t].append(e)
    return by_id, outgoing, incoming


def analyze_removal(nodes, edges, removed_id):
    """Propaga impacto. Um nó só bloqueia se todas as dependências equivalentes de entrada falharem.
    Para o dataset atual, SUPPLIES é tratado como redundância de fornecedor para Product.
    Demais relações propagam impacto como dependência observada, não como BOM física.
    """
    by_id, outgoing, incoming = build_indexes(nodes, edges)
    removed_id = str(removed_id)
    removed, blocked, at_risk = {removed_id}, set(), set()
    failed = {removed_id}
    q = deque([removed_id])

    while q:
        cur = q.popleft()
        for e in outgoing.get(cur, []):
            target = str(e['target'])
            if target in failed:
                continue
            inc = incoming.get(target, [])
            # Alternative predecessors of the same relationship type.
            same_type = [x for x in inc if x.get('type') == e.get('type')]
            alternatives = [x for x in same_type if str(x['source']) not in failed]
            if alternatives:
                at_risk.add(target)
                continue
            blocked.add(target); failed.add(target); q.append(target)

    # Orders that depend on a blocked Product point in the reverse direction in this schema.
    blocked_products = {x for x in blocked | removed if by_id.get(x, {}).get('label') == 'Product'}
    for pid in list(blocked_products):
        for e in incoming.get(pid, []):
            if e.get('type') == 'CONTAINS':
                oid = str(e['source'])
                blocked.add(oid); failed.add(oid)

    operational = set(by_id) - removed - blocked - at_risk
    return {'removed': removed, 'blocked': blocked, 'at_risk': at_risk, 'operational': operational}
