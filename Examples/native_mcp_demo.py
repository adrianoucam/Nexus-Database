"""MCP nativo: hospital sintético, cliente Python padrão e comparação com Agent API.

Inicia e encerra somente processos isolados; não usa a instalação da porta 7474.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import platform
from pathlib import Path
import time
import urllib.error
import urllib.request
from crypto_temporal_lab import NexusSession, REPO

DATABASE = 'EXAMPLE_MCP_HOSPITAL'

class MCPClient:
    def __init__(self, url, user, password, database):
        self.url = url.rstrip('/') + '/mcp'
        self.headers = {'X-User': user, 'X-Pass': password, 'X-Database': database,
                        'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
        self.counter = 0
    def request(self, method, params=None, notification=False, http_method='POST'):
        self.counter += 1
        message = {'jsonrpc': '2.0', 'method': method}
        if not notification:
            message['id'] = self.counter
        if params is not None:
            message['params'] = params
        req = urllib.request.Request(self.url, data=json.dumps(message).encode() if http_method == 'POST' else None,
                                     headers=self.headers, method=http_method)
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                if method == 'initialize':
                    self.headers['Mcp-Session-Id'] = response.headers['Mcp-Session-Id']
                raw = response.read()
                value = json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'MCP HTTP {error.code}: {error.read(2048).decode(errors="replace")}') from error
        if 'error' in value:
            raise RuntimeError(f'MCP protocol error: {value["error"]}')
        return value.get('result', {})
    def initialize(self):
        result = self.request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                            'clientInfo': {'name': 'nexusdb-python-demo', 'version': '0.1'}})
        self.headers['MCP-Protocol-Version'] = result['protocolVersion']
        self.request('notifications/initialized', notification=True)
        return result
    def call(self, name, arguments=None):
        result = self.request('tools/call', {'name': name, 'arguments': arguments or {}})
        if result.get('isError'):
            raise RuntimeError(f'Tool error: {result.get("structuredContent")}')
        return result['structuredContent']
    def close(self):
        if 'Mcp-Session-Id' in self.headers:
            self.request('', http_method='DELETE')
            self.headers.pop('Mcp-Session-Id', None)

def percentiles(samples):
    values = sorted(samples)
    def p(q):
        x = (len(values)-1)*q
        lo = int(x)
        return values[lo] + (values[min(lo+1, len(values)-1)]-values[lo])*(x-lo)
    return {'p50_ms': p(.5), 'p95_ms': p(.95), 'p99_ms': p(.99), 'samples_ms': samples}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=REPO/'target/debug/nexusdb.exe')
    parser.add_argument('--output', type=Path, default=Path('native-mcp-output'))
    parser.add_argument('--patients', type=int, default=20)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--samples', type=int, default=3, help='Chamadas por agente e condição')
    parser.add_argument('--concurrency', type=int, nargs='+', default=[1, 10])
    args = parser.parse_args()
    if not 2 <= args.patients <= 1000 or not 1 <= args.samples <= 100 or any(not 1 <= c <= 100 for c in args.concurrency):
        parser.error('patients: 2..1000; samples: 1..100; concurrency: 1..100')
    root = args.output.resolve()/f'run-{time.time_ns()}'
    root.mkdir(parents=True)
    aliases = ['nexus_schema','nexus_graph_stats','nexus_bfs','nexus_neighbors','nexus_shortest_path','nexus_pagerank']
    catalog = root/'mcp-catalog.json'
    catalog.write_text(json.dumps({'databases': {DATABASE: {'tools': aliases, 'users': ['mcp_reader']}}}), encoding='utf8')
    session = NexusSession(args.server.resolve(strict=True), root, database=DATABASE, environment={
        'NEXUSDB_MCP_ENABLED': 'true', 'NEXUSDB_MCP_CONFIG': str(catalog),
        'NEXUSDB_MCP_REQUESTS_PER_MINUTE': '100000'})
    client = None
    report = {'status': 'running', 'database': DATABASE, 'checks': [], 'benchmarks': [],
              'hardware': {'platform': platform.platform(), 'processor': platform.processor()},
              'server_binary': str(args.server.resolve()), 'patients': args.patients,
              'limitations': ['Dados sintéticos; tempos locais exploratórios, sem prova de ganho geral.',
                              'Compara MCP com Agent API HTTP; não mede MCP externo nem Rust direto.',
                              'CPU_SERIAL fixado na instância isolada; não mede GPU nem pico de memória.',
                              'Erros de admissão/taxa são contabilizados; não são amostras de sucesso.']}
    def check(name, condition):
        report['checks'].append({'name': name, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(name)
        print('OK:', name, flush=True)
    try:
        nodes = [{'key': 'doctor', 'label': 'Doctor', 'properties': {'name': 'Dra. Ana'}}]
        nodes += [{'key': f'p{i}', 'label': 'Patient', 'properties': {'name': f'Paciente {i}'}} for i in range(args.patients)]
        created = session.request('/db/data/node/bulk', {'rows': nodes})['resultados']
        ids = {row['key']: row['id'] for row in created}
        session.request('/db/data/relationship/bulk', {'rows': [
            {'key': f'a{i}', 'from': ids['doctor'], 'to': ids[f'p{i}'], 'type': 'ATTENDS', 'properties': {}}
            for i in range(args.patients)]})
        password = __import__('secrets').token_urlsafe(32)
        session.request('/db/admin/user/create', {'username': 'mcp_reader', 'password': password, 'role': 'user', 'expires_days': 0})
        session.request('/db/admin/grant', {'username': 'mcp_reader', 'database': DATABASE, 'access': 'READ'})
        client = MCPClient(session.url, 'mcp_reader', password, DATABASE)
        report['initialize'] = client.initialize()
        tools = client.request('tools/list')['tools']
        report['tools'] = tools
        check('Catálogo autorizado contém seis ferramentas', {t['name'] for t in tools} == set(aliases))
        report['schema'] = client.call('nexus_schema')
        check('Schema nativo retornou objeto', isinstance(report['schema'], dict))
        report['stats'] = client.call('nexus_graph_stats')
        report['neighbors'] = client.call('nexus_neighbors', {'source': ids['doctor'], 'limit': min(args.patients, 100)})
        check('Vizinhos respeitam limite e sinalizam truncamento', len(report['neighbors']['resultados']) == min(args.patients, 100)
              and report['neighbors']['truncated'] == (args.patients > 100))
        report['bfs'] = client.call('nexus_bfs', {'source': ids['doctor'], 'max_depth': 1, 'limit': min(args.patients+1,100)})
        check('BFS inclui origem e pacientes', len(report['bfs']['resultados']) == min(args.patients+1,100))
        report['path'] = client.call('nexus_shortest_path', {'source': ids['p0'], 'target': ids['p1']})
        check('Caminho entre pacientes passa pela médica', report['path']['path'] == [ids['p0'],ids['doctor'],ids['p1']])
        report['pagerank'] = client.call('nexus_pagerank', {'iterations': 20, 'limit': min(args.patients+1,100)})
        native = session.request('/agent/tool/algo.pagerank', {'input': {'iterations': 20, 'limit': min(args.patients+1,100)}}, user='mcp_reader', password=password)
        check('PageRank MCP coincide com executor Agent API', report['pagerank']['resultados'] == native['result']['resultados'])
        try:
            client.request('tools/call', {'name': 'nexus_create_vertex', 'arguments': {}})
        except RuntimeError:
            check('Escrita não publicada é recusada', True)
        else:
            check('Escrita não publicada é recusada', False)
        if args.benchmark:
            for count in args.concurrency:
                for mode in ['mcp', 'agent_http']:
                    def agent(_):
                        local = MCPClient(session.url, 'mcp_reader', password, DATABASE)
                        if mode == 'mcp':
                            local.initialize()
                        durations, errors = [], []
                        try:
                            for _ in range(args.samples):
                                start = time.perf_counter()
                                try:
                                    if mode == 'mcp':
                                        local.call('nexus_graph_stats')
                                    else:
                                        session.request('/agent/tool/database.stats', {'input': {}}, user='mcp_reader', password=password)
                                    durations.append((time.perf_counter()-start)*1000)
                                except RuntimeError as error:
                                    errors.append(str(error)[:200])
                        finally:
                            if mode == 'mcp':
                                local.close()
                        return durations, errors
                    start = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=count) as pool:
                        results = list(pool.map(agent, range(count)))
                    elapsed = time.perf_counter()-start
                    durations = [v for values,_ in results for v in values]
                    errors = [v for _,values in results for v in values]
                    report['benchmarks'].append({'mode': mode, 'concurrency': count,
                        'requested_calls': count*args.samples, 'successes': len(durations), 'errors': errors,
                        'status': 'measured_with_rejections' if errors else 'measured',
                        'elapsed_s_including_sessions': elapsed, 'successful_throughput_per_s': len(durations)/elapsed,
                        **(percentiles(durations) if durations else {})})
        report['status'] = 'passed'
    except Exception:
        report['status'] = 'failed'
        raise
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            session.close()
            (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('Relatório:', root/'report.json')

if __name__ == '__main__':
    main()
