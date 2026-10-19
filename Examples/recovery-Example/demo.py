"""Mede perda de escritas HTTP após kill/restart de processos NexusDB próprios."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import time

EXAMPLES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLES))
from crypto_temporal_lab import NexusSession


class Instance(NexusSession):
    def __init__(self, binary, root, durable):
        self.binary, self.root = binary, root
        self.database = 'EXAMPLE_RECOVERY'
        self.password = secrets.token_urlsafe(32)
        self.trace = []
        self.process = None
        self.log = (root / 'server.log').open('a', encoding='utf8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.url = f'http://127.0.0.1:{self.port}'
        self.env = os.environ | {'NEXUSDB_DATA_ROOT': str(root / 'data'),
            'NEXUSDB_HTTP_ADDR': f'127.0.0.1:{self.port}', 'NEXUSDB_ADMIN_PASSWORD': self.password,
            'NEXUSDB_MODE': 'SINGLE', 'NEXUSDB_CUDA_ENABLED': 'false',
            'NEXUSDB_COMPUTE_BACKEND': 'CPU_SERIAL', 'NEXUSDB_QUERY_CACHE': 'false',
            'NEXUSDB_SQLITE_BATCH_SIZE': '1' if durable else '1000',
            'NEXUSDB_RECOVERY_JOURNAL': '1' if durable else '0'}

    def start(self):
        start = time.perf_counter()
        self.process = subprocess.Popen([str(self.binary)], cwd=self.root, env=self.env,
            stdout=self.log, stderr=self.log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        for _ in range(300):
            if self.process.poll() is not None:
                raise RuntimeError('Servidor encerrou; consulte server.log')
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=.1):
                    pass
                return round((time.perf_counter() - start) * 1000, 3)
            except Exception:
                time.sleep(.1)
        raise TimeoutError('Servidor não ficou pronto')

    def crash(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=15)

    def close(self):
        self.crash()
        self.log.close()


def rows_for(prefix, count):
    return [{'key': f'{prefix}-{i}', 'label': 'RecoveryProbe',
             'properties': {'probe': f'{prefix}-{i}', 'value': i}} for i in range(count)]


def scan(instance):
    rows = instance.request('/db/data/node/search', {'label': 'RecoveryProbe', 'limit': 10000})['rows']
    return {r['properties']['probe']: r['properties']['value'] for r in rows}


def integrity(root):
    results = []
    # Somente com o processo parado. Nunca abrir arquivos da instalação real.
    for path in (root / 'data').rglob('*'):
        if not path.is_file() or path.suffix in ('.wal', '.shm'):
            continue
        with path.open('rb') as file:
            signature = file.read(16)
        if signature != b'SQLite format 3\x00':
            continue
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
            result = [r[0] for r in conn.execute('PRAGMA integrity_check')]
        results.append({'file': str(path.relative_to(root)), 'result': result})
    return results


def run_profile(binary, root, profile, rounds, count):
    root.mkdir()
    instance = Instance(binary, root, profile == 'journal_full_batch1')
    report = {'profile': profile, 'rounds': [], 'status': 'running',
        'configuration': {'batch_size': instance.env['NEXUSDB_SQLITE_BATCH_SIZE'],
                          'recovery_journal': instance.env['NEXUSDB_RECOVERY_JOURNAL'], 'temporal_history': False}}
    acknowledged = {}
    try:
        instance.start()
        instance.request('/db/admin/database/create', {'database': instance.database, 'temporal_history': False})
        # Pedido inválido: observar se o primeiro item de um lote rejeitado vaza.
        malformed = rows_for('invalid-batch', 1) + [{'key': 'bad', 'properties': {}}]
        rejected = False
        try:
            instance.request('/db/data/node/bulk', {'rows': malformed})
        except RuntimeError:
            rejected = True
        report['invalid_batch'] = {'rejected': rejected, 'partial_visible': 'invalid-batch-0' in scan(instance)}
        for cycle in range(rounds):
            batch = rows_for(f'confirmed-{cycle}', count)
            reply = instance.request('/db/data/node/bulk', {'rows': batch})
            if reply['processados'] != count:
                raise RuntimeError('Confirmação parcial de escrita')
            acknowledged.update({r['properties']['probe']: r['properties']['value'] for r in batch})
            # Leitura em outra conexão HTTP deve observar o lote confirmado.
            visible = scan(instance)
            read_after_write = all(visible.get(k) == v for k, v in acknowledged.items())
            instance.crash()
            checks = integrity(root)
            restart_ms = instance.start()
            recovered = scan(instance)
            missing = sorted(k for k in acknowledged if k not in recovered)
            changed = sorted(k for k, v in acknowledged.items() if k in recovered and recovered[k] != v)
            report['rounds'].append({'cycle': cycle, 'acknowledged_total': len(acknowledged),
                'read_after_write': read_after_write, 'lost_acknowledged': missing,
                'changed_values': changed, 'restart_socket_ready_ms': restart_ms, 'sqlite_integrity': checks})
            print(f'{profile} ciclo {cycle + 1}: confirmados={len(acknowledged)} perdidos={len(missing)} alterados={len(changed)}', flush=True)
        # Interromper uma requisição em andamento: resultado desconhecido não é perda confirmada.
        pending = rows_for('inflight', 500)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(instance.request, '/db/data/node/bulk', {'rows': pending})
            time.sleep(.01)
            instance.crash()
            try:
                response = future.result(timeout=65)
                confirmed = response.get('processados') == len(pending)
            except Exception:
                confirmed = False
        instance.start()
        recovered = scan(instance)
        present = sum(r['properties']['probe'] in recovered for r in pending)
        report['inflight'] = {'http_success_received': confirmed, 'submitted': len(pending), 'recovered': present,
            'all_or_none_observed': present in (0, len(pending)),
            'lost_if_confirmed': len(pending) - present if confirmed else None,
            'outcome': 'confirmed' if confirmed else 'unknown_to_client'}
        report['inflight']['lost_prior_acknowledged'] = sorted(k for k in acknowledged if k not in recovered)
        report['inflight']['changed_prior_values'] = sorted(k for k, v in acknowledged.items() if k in recovered and recovered[k] != v)
        durable_ok = all(not r['lost_acknowledged'] and not r['changed_values'] and r['read_after_write']
                         and r['sqlite_integrity'] and all(c['result'] == ['ok'] for c in r['sqlite_integrity']) for r in report['rounds'])
        durable_ok = durable_ok and not report['inflight']['lost_prior_acknowledged'] and not report['inflight']['changed_prior_values']
        atomic_ok = rejected and not report['invalid_batch']['partial_visible'] and report['inflight']['all_or_none_observed']
        report['status'] = 'passed_observed_scope' if durable_ok and atomic_ok and not report['inflight']['lost_if_confirmed'] else 'failed'
    except BaseException as error:
        report.update(status='failed', failure_type=type(error).__name__)
        raise
    finally:
        instance.close()
        (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create-lab', action='store_true', required=True)
    parser.add_argument('--server', type=Path, default=EXAMPLES.parent / 'target/debug/nexusdb.exe')
    parser.add_argument('--output', type=Path, default=EXAMPLES.parent / 'target/recovery-validation')
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--rows', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10 or not 1 <= args.rows <= 100:
        parser.error('rounds: 1..10; rows: 1..100')
    binary = args.server.resolve(strict=True)
    root = args.output.resolve() / f'run-{time.time_ns()}'
    root.mkdir(parents=True)
    report = {'scope': 'process_crash_only_not_power_loss_or_full_ACID', 'profiles': [],
              'limitations': ['Não prova isolamento serializável, transações multi-HTTP ou falha física de disco/energia.',
                  'Atomicidade observada em lote rejeitado e escrita interrompida, não em todas as operações.',
                  'Tempo mede socket aberto após lançar processo; leitura autenticada é verificada depois. Não é SLA.',
                  'Configuração efetiva de SQLite deve ser auditada no servidor; perfis registram valores solicitados.']}
    try:
        for profile in ['batch1000_journal_off', 'journal_full_batch1']:
            report['profiles'].append(run_profile(binary, root / profile, profile, args.rounds, args.rows))
    finally:
        report['status'] = 'passed_observed_scope' if len(report['profiles']) == 2 and all(p['status'] == 'passed_observed_scope' for p in report['profiles']) else 'failed'
        (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        print('Relatório:', root / 'report.json', flush=True)
    if report['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
