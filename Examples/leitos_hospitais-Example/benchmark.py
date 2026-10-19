"""Executar: python benchmark.py --output benchmark_resultado.json"""
import argparse
import hashlib
import json
import platform
import statistics
import time
import tracemalloc
from datetime import datetime
from pathlib import Path
from optimization import load, snapshot, solve, audit, benefit

METHODS = ('convencional', 'matching', 'fluxo_custo_minimo', 'genetico', 'robusto')


def positive(value):
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError('Use um inteiro entre 1 e 100')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).with_name('HSJA_dataset_simulado_outubro_2026.zip'))
    parser.add_argument('--at', default='2026-10-15 12:00:00')
    parser.add_argument('--iterations', type=positive, default=3)
    parser.add_argument('--generations', type=positive, default=20)
    parser.add_argument('--seed', type=int, default=20261008)
    parser.add_argument('--blocked', default='', help='IDs de leitos indisponíveis separados por vírgula')
    parser.add_argument('--output', type=Path, default=Path('benchmark_resultado.json'))
    args = parser.parse_args()
    at = datetime.fromisoformat(args.at)
    if not datetime(2026, 10, 1) <= at < datetime(2026, 11, 1):
        parser.error('--at deve estar em outubro de 2026')
    start = time.perf_counter()
    data = load(args.dataset)
    blocked = set(filter(None, args.blocked.split(',')))
    if blocked - {b['leito_id'] for b in data['leitos']}:
        parser.error('--blocked contém leito inexistente')
    requests, beds, forecast = snapshot(data, at, blocked)
    snapshot_ms = (time.perf_counter() - start) * 1000
    report = {'synthetic_only': True, 'at': args.at, 'seed': args.seed,
              'dataset_sha256': hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
              'environment': {'os': platform.platform(), 'cpu': platform.processor(),
                              'python': platform.python_version(), 'build': 'Python interpreter'},
              'selected_backend': 'SERIAL_CPU', 'reason': 'Implementação experimental Python stdlib',
              'gpu': None, 'snapshot_ms': snapshot_ms, 'cache_state': 'snapshot carregado uma vez; solves sem cache',
              'volumes': {k: len(v) for k, v in data.items()},
              'available_beds': len(beds), 'eligible_requests': len(requests),
              'forecast_daily': forecast, 'blocked': sorted(blocked), 'results': []}
    for method in METHODS:
        timings, peaks = [], []
        for _ in range(args.iterations):
            tracemalloc.start()
            started = time.perf_counter()
            result = solve(method, requests, beds, at, forecast, args.seed, args.generations)
            timings.append((time.perf_counter() - started) * 1000)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
            audit(result, requests, beds)
        assignments = [{'solicitacao_id': requests[i]['solicitacao_id'],
                        'paciente_id': requests[i]['paciente_id'], 'leito_id': beds[j]['leito_id'],
                        'quarto_id': beds[j]['quarto_id']} for i, j in sorted(result.items())]
        report['results'].append({'method': method, 'iterations': args.iterations,
            'p50_ms': statistics.median(timings),
            'p95_ms': sorted(timings)[max(0, __import__('math').ceil(.95 * len(timings)) - 1)],
            'peak_python_bytes': max(peaks), 'allocated': len(result),
            'pending': len(requests) - len(result), 'benefit': sum(benefit(requests[i], at) for i in result),
            'urgent_allocated': sum(requests[i]['prioridade'] == 'URGENTE' for i in result),
            'hard_violations': 0, 'assignments': assignments})
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for row in report['results']:
        print(f"{row['method']}: {row['allocated']} alocações, {row['pending']} pendências; p50={row['p50_ms']:.2f} ms")
    print(args.output.resolve())


if __name__ == '__main__':
    main()
