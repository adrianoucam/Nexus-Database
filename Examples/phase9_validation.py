"""Out-of-core validation in a NEW data root; no production services or credentials.
Requires pyarrow and psutil. Duration is validation evidence, not a comparative benchmark.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.request
import psutil
import pyarrow as pa
import pyarrow.ipc as ipc
from arrow_client import batches as remote_batches

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--server', type=Path)
    parser.add_argument('--output', type=Path, default=Path('phase9-demo-output'))
    parser.add_argument('--nodes', type=int, default=100000)
    parser.add_argument('--fanout', type=int, default=32)
    parser.add_argument('--history', action='store_true')
    args = parser.parse_args()
    if not 32 <= args.nodes <= 1000000 or not 1 <= args.fanout <= 128:
        raise ValueError('nodes must be 32..1000000 and fanout 1..128')
    binary = args.binary.resolve(strict=True)
    root = args.output.resolve() / ('run-' + str(time.time_ns()))
    root.mkdir(parents=True, exist_ok=False)
    db = 'EXAMPLE_PARTITIONED'
    env = os.environ.copy()
    env.update(NEXUSDB_DATA_ROOT=str(root / 'data'), NEXUSDB_RESOURCES_MEMORY_MB='32',
               NEXUSDB_COMPUTE_MEMORY_MB='32', NEXUSDB_MODE='SINGLE',
               NEXUSDB_COMPUTE_BACKEND='CPU_SERIAL', NEXUSDB_CUDA_ENABLED='false',
               NEXUSDB_COMPUTE_TIMEOUT_MS='300000', NEXUSDB_HTTP_IO_TIMEOUT_SECS='300')
    env.pop('NEXUSDB_RECOVERY_JOURNAL', None)
    measurements = []
    def run(operation, *arguments):
        start = time.monotonic()
        print('Starting:', operation, flush=True)
        with (root / (operation + '.stdout')).open('w', encoding='utf8') as stdout, \
             (root / (operation + '.stderr')).open('w', encoding='utf8') as stderr:
            process = subprocess.Popen([str(binary), operation, db, *map(str, arguments)],
                env=env, cwd=root, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            monitored = psutil.Process(process.pid)
            peak = 0
            while process.poll() is None:
                try:
                    peak = max(peak, monitored.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                time.sleep(.02)
            if process.returncode:
                raise RuntimeError((root / (operation + '.stderr')).read_text(encoding='utf8'))
        value = json.loads((root / (operation + '.stdout')).read_text(encoding='utf8'))
        measurements.append({'operation': operation, 'peak_rss_bytes': peak,
                             'seconds': time.monotonic() - start})
        (root / 'measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf8')
        print('Passed:', operation, 'peak RSS:', peak, flush=True)
        return value
    nodes, edges = root / 'nodes.jsonl', root / 'relationships.jsonl'
    with nodes.open('w', encoding='utf8') as stream:
        for i in range(1, args.nodes + 1):
            stream.write(json.dumps({'id': i, 'label': 'Simulated', 'properties':
                {'risk': i % 5, 'name': 'Simulated-' + str(i), 'payload': 'x' * 512}}, separators=(',', ':')) + '\n')
    total_edges = 0
    with edges.open('w', encoding='utf8') as stream:
        def edge(a, b):
            nonlocal total_edges
            total_edges += 1
            stream.write(json.dumps({'id': total_edges, 'node_a': a, 'node_b': b,
                'rel_type': 'LINK', 'properties': {'layer': 'simulation'}}, separators=(',', ':')) + '\n')
        for i in range(2, args.nodes + 1):
            edge(1, i)
        for i in range(1, args.nodes + 1):
            for j in range(1, args.fanout + 1):
                edge(i, (i + j - 1) % args.nodes + 1)
    imported = run('import', nodes, edges, *(['--history'] if args.history else []))
    assert imported['nodes'] == args.nodes and imported['relationships'] == total_edges
    built = run('build', 'main', json.dumps({'layers': ['simulation']}), 2048)
    assert built['manifest']['nodes'] == args.nodes and built['manifest']['edges'] == total_edges
    bfs = run('bfs', 'main', 1, 4, args.nodes + 1)
    assert bfs['visited'] == args.nodes and not bfs['truncated'], bfs
    assert bfs['results_truncated'] and bfs['frontier_storage'] == 'sqlite_disk'
    assert all(row['depth'] == (0 if row['node_id'] == 1 else 1) for row in bfs['resultados'])
    # Checkpoint after import is optional because large topology validation does not require history.
    if args.history:
        checkpoint = run('checkpoint')
        assert checkpoint['rows'] == args.nodes + total_edges
    request = root / 'arrow-request.json'
    request.write_text(json.dumps({'export_id': 'properties', 'entity': 'nodes',
        'columns': [{'name': 'risk', 'field': 'risk', 'data_type': 'int64'},
                    {'name': 'name', 'field': 'name', 'data_type': 'utf8'}],
        'batch_rows': 512, 'batch_bytes': 1048576}), encoding='utf8')
    exported = run('arrow', request)
    assert exported['rows'] == args.nodes
    arrow = root / 'data' / db / 'arrow' / 'properties' / 'properties.arrow'
    count = 0
    with pa.memory_map(str(arrow), 'r') as mapped:
        magic = mapped.read(6)
        mapped.seek(0)
        reader = ipc.open_file(mapped) if magic == b'ARROW1' else ipc.open_stream(mapped)
        assert reader.schema.field('risk').type == pa.int64()
        assert reader.schema.metadata[b'nexusdb.contract'] == b'properties-v1'
        batches = (reader.get_batch(i) for i in range(reader.num_record_batches)) if hasattr(reader, 'num_record_batches') else reader
        for i, batch in enumerate(batches):
            assert batch.num_rows <= 512
            count += batch.num_rows
            if i == 0:
                assert batch.column('risk')[0].as_py() == 1
                assert batch.column('name')[0].as_py() == 'Simulated-1'
    assert count == args.nodes
    server_check = None
    if args.server:
        server_binary = args.server.resolve(strict=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        password = secrets.token_urlsafe(32)
        server_env = env | {'NEXUSDB_HTTP_ADDR': f'127.0.0.1:{port}', 'NEXUSDB_ADMIN_PASSWORD': password}
        peak = [0]
        done = threading.Event()
        with (root / 'server.log').open('w', encoding='utf8') as log:
            process = subprocess.Popen([str(server_binary)], env=server_env, cwd=root,
                stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            def sample():
                monitored = psutil.Process(process.pid)
                while not done.wait(.02):
                    try:
                        peak[0] = max(peak[0], monitored.memory_info().rss)
                    except psutil.NoSuchProcess:
                        break
            monitor = threading.Thread(target=sample)
            monitor.start()
            try:
                for _ in range(200):
                    if process.poll() is not None:
                        raise RuntimeError('Isolated server failed; inspect server.log')
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise TimeoutError('Isolated server startup')
                def query(text):
                    body = json.dumps({'statements': [{'query': text}]}).encode()
                    request = urllib.request.Request(f'http://127.0.0.1:{port}/db/data/cypher', body,
                        headers={'X-User': 'admin', 'X-Pass': password, 'X-Database': db,
                                 'Content-Type': 'application/json'})
                    with urllib.request.urlopen(request, timeout=300) as response:
                        return json.load(response)
                result = query('CALL graph.partitionBfs({snapshot_id:"main",source:1,max_depth:4,max_visited:' + str(args.nodes + 1) + ',limit:10}) YIELD visited RETURN visited')
                assert result['resultados'][0]['visited'] == args.nodes and not result.get('errors'), result
                denied = query('MATCH (n:Simulated) RETURN n')
                assert denied.get('errors') and 'DISK_ONLY_UNSUPPORTED' in denied['errors'][0]['error'], denied
                downloaded = sum(batch.num_rows for batch in remote_batches(
                    f'http://127.0.0.1:{port}', db, 'admin', password, 'properties'))
                assert downloaded == args.nodes
                server_check = {'visited': args.nodes, 'legacy_query_rejected': True,
                                'python_arrow_http_rows': downloaded,
                                'peak_rss_bytes': peak[0]}
            finally:
                process.terminate()
                process.wait(timeout=15)
                done.set()
                monitor.join()
    topology_bytes = sum(path.stat().st_size for path in (root / 'data' / db / 'partitions' / 'main').glob('*.csr'))
    peak = max([m['peak_rss_bytes'] for m in measurements] + ([server_check['peak_rss_bytes']] if server_check else []))
    report = {'passed': True, 'nodes': args.nodes, 'relationships': total_edges,
        'managed_memory_limit_bytes': 32 * 1024 * 1024, 'csr_binary_bytes': topology_bytes,
        'csr_exceeds_managed_budget': topology_bytes > 32 * 1024 * 1024,
        'csr_exceeds_measured_process_rss': topology_bytes > peak,
        'peak_process_rss_bytes': peak, 'measurements': measurements,
        'server': server_check, 'python_arrow_rows': count, 'pyarrow_version': pa.__version__,
        'notes': ['Synthetic data only.', 'RSS includes runtime and unmanaged allocations; the managed budget is not an OS process cap.',
                  'No device type detection: this is not an NVMe throughput benchmark.']}
    (root / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2))
    print('Report:', root / 'report.json')

if __name__ == '__main__':
    main()
