"""Benchmark experimental HSJA: somente dados fictícios, Python stdlib, CPU."""
import csv
import io
import math
import random
import zipfile
from collections import Counter
from datetime import datetime, timedelta

PRIORITY = {'URGENTE': 3, 'ALTA': 2, 'ROTINA': 1}


def load(path):
    with zipfile.ZipFile(path) as archive:
        return {name[:-4]: list(csv.DictReader(io.StringIO(
            archive.read(name).decode('utf-8-sig')), delimiter=';'))
            for name in archive.namelist() if name.endswith('.csv')}


def snapshot(data, at, blocked=()):
    """Intervalos semiabertos; alta não libera leito antes da limpeza."""
    stamp = at.strftime('%Y-%m-%d %H:%M:%S')
    unavailable = set(blocked)
    patients = set()
    cleaning = {r['internacao_anterior_id']: r['fim'] for r in data['higienizacoes']}
    for row in data['internacoes']:
        if row['entrada_leito'] <= stamp:
            end = row['saida_leito']
            if not end or stamp < end:
                patients.add(row['paciente_id'])
            release = cleaning.get(row['internacao_id'])
            # Ausência de limpeza após saída: bloqueio conservador.
            if not end or not release or stamp < release:
                unavailable.add(row['leito_id'])
    for row in data['higienizacoes']:
        if row['inicio'] <= stamp < row['fim']:
            unavailable.add(row['leito_id'])
    beds = sorted((r for r in data['leitos'] if r['ativo'] == '1'
                   and r['leito_id'] not in unavailable), key=lambda r: r['leito_id'])
    requests, seen = [], set(patients)
    eligible = sorted((r for r in data['solicitacoes_pendentes']
                       if r['entrada'] <= stamp and r['status'] == 'PENDENTE_SIMULADA'),
                      key=lambda r: (r['entrada'], r['solicitacao_id']))
    for row in eligible:
        if row['paciente_id'] not in seen:
            requests.append(row)
            seen.add(row['paciente_id'])
    # Média diária dos sete dias anteriores, sem olhar o futuro.
    history = Counter(r['unidade_id'] for r in data['internacoes']
                      if (at - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                      <= r['entrada_leito'] < stamp)
    forecast = {unit: count / 7 for unit, count in history.items()}
    return requests, beds, forecast


def compatible(request, bed):
    return (request['unidade_requerida'] == bed['unidade_id']
            and (not request.get('isolamento_indicado') == '1'
                 or bed['suporte_isolamento'] == '1')
            and (not request.get('ventilador_requerido') == '1'
                 or bed['ventilador'] == '1'))


def benefit(request, at):
    wait = max(0, (at - datetime.fromisoformat(request['entrada'])).total_seconds() / 3600)
    return PRIORITY[request['prioridade']] * 10000 + min(9999, int(wait * 10))


def greedy(requests, beds, order):
    available = list(range(len(beds)))
    result = {}
    for i in order:
        j = next((j for j in available if compatible(requests[i], beds[j])), None)
        if j is not None:
            result[i] = j
            available.remove(j)
    return result


def matching(requests, beds):
    owner = {}
    def augment(i, seen):
        for j, bed in enumerate(beds):
            if j in seen or not compatible(requests[i], bed):
                continue
            seen.add(j)
            if j not in owner or augment(owner[j], seen):
                owner[j] = i
                return True
        return False
    for i in range(len(requests)):
        augment(i, set())
    return {i: j for j, i in owner.items()}


def min_cost(requests, beds, at):
    """Fluxo unitário de cardinalidade máxima; custo negativo prioriza benefícios."""
    n, m = len(requests), len(beds)
    source, sink = n + m, n + m + 1
    graph = [[] for _ in range(sink + 1)]
    def edge(a, b, cost):
        graph[a].append([b, len(graph[b]), 1, cost])
        graph[b].append([a, len(graph[a]) - 1, 0, -cost])
    for i, request in enumerate(requests):
        edge(source, i, -benefit(request, at))
        for j, bed in enumerate(beds):
            if compatible(request, bed):
                edge(i, n + j, 0)
    for j in range(m):
        edge(n + j, sink, 0)
    while True:
        distance = [math.inf] * len(graph)
        parent = [None] * len(graph)
        distance[source] = 0
        # Bellman-Ford aceita custos negativos e arestas residuais.
        for _ in range(len(graph) - 1):
            changed = False
            for a, edges in enumerate(graph):
                if distance[a] == math.inf:
                    continue
                for k, (b, _, capacity, cost) in enumerate(edges):
                    if capacity and distance[a] + cost < distance[b]:
                        distance[b], parent[b] = distance[a] + cost, (a, k)
                        changed = True
            if not changed:
                break
        if parent[sink] is None:
            break
        b = sink
        while b != source:
            a, k = parent[b]
            e = graph[a][k]
            e[2] -= 1
            graph[b][e[1]][2] += 1
            b = a
    return {i: e[0] - n for i in range(n) for e in graph[i]
            if n <= e[0] < n + m and e[2] == 0}


def genetic(requests, beds, at, seed, generations):
    rng = random.Random(seed)
    base = sorted(range(len(requests)), key=lambda i: -benefit(requests[i], at))
    population = [base]
    for _ in range(15):
        order = base.copy()
        rng.shuffle(order)
        population.append(order)
    def score(order):
        result = greedy(requests, beds, order)
        return len(result), sum(benefit(requests[i], at) for i in result)
    for _ in range(generations):
        population.sort(key=score, reverse=True)
        survivors = population[:4]
        children = []
        for _ in range(12):
            a, b = rng.sample(survivors, 2)
            cut = rng.randrange(len(a) + 1)
            child = a[:cut]
            present = set(child)
            child += [i for i in b if i not in present]
            if len(child) > 1:
                x, y = rng.sample(range(len(child)), 2)
                child[x], child[y] = child[y], child[x]
            children.append(child)
        population = survivors + children
    return greedy(requests, beds, max(population, key=score))


def solve(method, requests, beds, at, forecast, seed=20261008, generations=20):
    if method == 'convencional':
        return greedy(requests, beds, range(len(requests)))
    if method == 'matching':
        return matching(requests, beds)
    if method == 'fluxo_custo_minimo':
        return min_cost(requests, beds, at)
    if method == 'genetico':
        return genetic(requests, beds, at, seed, generations)
    if method == 'robusto':
        # Pior cenário entre 0.8x, 1x, 1.2x: reservar demanda de 6h.
        reserve = {u: math.ceil(v * 1.2 / 4) for u, v in forecast.items()}
        order = sorted(range(len(requests)), key=lambda i: -benefit(requests[i], at))
        result, available = {}, list(range(len(beds)))
        for i in order:
            r = requests[i]
            candidates = [j for j in available if compatible(r, beds[j])]
            if candidates and (r['prioridade'] == 'URGENTE'
                               or len(candidates) > reserve.get(r['unidade_requerida'], 0)):
                result[i] = candidates[0]
                available.remove(candidates[0])
        return result
    raise ValueError('Método desconhecido')


def audit(result, requests, beds):
    if len(set(result.values())) != len(result):
        raise ValueError('Leito duplicado')
    if len({requests[i]['paciente_id'] for i in result}) != len(result):
        raise ValueError('Paciente duplicado')
    if any(not compatible(requests[i], beds[j]) for i, j in result.items()):
        raise ValueError('Alocação incompatível')
