"""Painel local de leitos fictícios HSJA. Python 3.10+, sem dependências."""
import argparse
import json
import secrets
import time
import webbrowser
from collections import OrderedDict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from optimization import load, snapshot, solve, audit, benefit, compatible
from benchmark import METHODS


class Hospital:
    def __init__(self, path):
        self.data = load(path)
        self.cache = OrderedDict()

    def view(self, day, hour, method, blocked=()):
        if type(day) is not int or not 1 <= day <= 31:
            raise ValueError('Dia deve estar entre 1 e 31')
        if type(hour) is not int or not 0 <= hour <= 23:
            raise ValueError('Hora deve estar entre 0 e 23')
        if method not in METHODS:
            raise ValueError('Modo inválido')
        if not isinstance(blocked, (list, tuple)) or not all(isinstance(b, str) for b in blocked):
            raise ValueError('Lista de bloqueios inválida')
        blocked = tuple(sorted(set(blocked)))
        if set(blocked) - {b['leito_id'] for b in self.data['leitos']}:
            raise ValueError('Leito bloqueado inexistente')
        key = day, hour, method, blocked
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        start = time.perf_counter()
        at = datetime(2026, 10, day, hour)
        stamp = at.strftime('%Y-%m-%d %H:%M:%S')
        requests, available, forecast = snapshot(self.data, at, blocked)
        result = solve(method, requests, available, at, forecast)
        audit(result, requests, available)
        assigned = {available[j]['leito_id']: requests[i] for i, j in result.items()}
        free = {b['leito_id'] for b in available}
        occupied = {r['leito_id']: r for r in self.data['internacoes']
                    if r['entrada_leito'] <= stamp and (not r['saida_leito'] or stamp < r['saida_leito'])}
        cleaning = {r['leito_id']: r for r in self.data['higienizacoes']
                    if r['inicio'] <= stamp < r['fim']}
        beds = []
        for bed in self.data['leitos']:
            item = dict(bed)
            bid = bed['leito_id']
            episode = occupied.get(bid)
            proposal = assigned.get(bid)
            state = ('ocupado' if episode else 'inativo' if bed['ativo'] != '1'
                     else 'bloqueado' if bid in blocked else 'limpeza' if bid in cleaning
                     else 'proposta' if proposal else 'livre' if bid in free else 'bloqueado')
            item.update(state=state, episode=episode, proposal=proposal,
                        cleaning=cleaning.get(bid), scenario_blocked=bid in blocked)
            beds.append(item)
        pending = [dict(r, motivo='Sem leito compatível disponível' if not any(
            compatible(r, b) for b in available)
            else 'Capacidade disputada / reserva de demanda' if method == 'robusto'
            else 'Capacidade disputada por outras solicitações')
            for i, r in enumerate(requests) if i not in result]
        response = {'day': day, 'hour': hour, 'at': stamp, 'method': method,
            'beds': beds, 'pending': pending, 'forecast': forecast,
            'metrics': {'occupied': len(occupied), 'cleaning': len(cleaning),
                'available': len(available), 'allocated': len(result), 'pending': len(pending),
                'urgent': sum(requests[i]['prioridade'] == 'URGENTE' for i in result),
                'benefit': sum(benefit(requests[i], at) for i in result),
                'hard_violations': 0, 'total_ms': (time.perf_counter() - start) * 1000},
            'backend': 'SERIAL_CPU', 'seed': 20261008, 'synthetic_only': True}
        self.cache[key] = response
        if len(self.cache) > 160:
            self.cache.popitem(last=False)
        return response

    def month(self, hour, method, blocked=()):
        return [{'day': day, **self.view(day, hour, method, blocked)['metrics']}
                for day in range(1, 32)]

    def timeline(self, bed_id):
        if bed_id not in {b['leito_id'] for b in self.data['leitos']}:
            raise ValueError('Leito inexistente')
        return {'admissions': [r for r in self.data['internacoes'] if r['leito_id'] == bed_id],
                'cleaning': [r for r in self.data['higienizacoes'] if r['leito_id'] == bed_id]}


def make_server(hospital, port):
    token = secrets.token_urlsafe(32)
    page = Path(__file__).with_name('index.html').read_text(encoding='utf-8').replace('__TOKEN__', token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, value, content_type='application/json'):
            body = (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)).encode('utf-8')
            self.send_response(status)
            for key, val in [('Content-Type', content_type + '; charset=utf-8'),
                             ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
                             ('X-Content-Type-Options', 'nosniff')]:
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(body)

        def local(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.local():
                return self.reply(403, {'error': 'Host inválido'})
            if self.path == '/':
                return self.reply(200, page, 'text/html')
            self.reply(404, {'error': 'Não encontrado'})

        def do_POST(self):
            if not self.local() or self.headers.get('X-Demo-Token') != token:
                return self.reply(403, {'error': 'Sessão inválida; recarregue a página'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError('Requisição deve ter até 16 KiB')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Objeto JSON esperado')
                if self.path == '/timeline':
                    return self.reply(200, hospital.timeline(payload['bed']))
                args = payload['day'], payload['hour'], payload['method'], payload.get('blocked', [])
                if self.path == '/view':
                    return self.reply(200, hospital.view(*args))
                if self.path == '/month':
                    hospital.view(*args)  # Valida todos os parâmetros antes do mês.
                    return self.reply(200, hospital.month(args[1], args[2], args[3]))
                if self.path == '/compare':
                    hospital.view(*args)
                    return self.reply(200, [{'method': m, **hospital.view(args[0], args[1], m, args[3])['metrics']}
                                            for m in METHODS])
                self.reply(404, {'error': 'Não encontrado'})
            except (ValueError, KeyError, TypeError) as error:
                self.reply(400, {'error': str(error)})

    return HTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).with_name('HSJA_dataset_simulado_outubro_2026.zip'))
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    hospital = Hospital(args.dataset)
    server = make_server(hospital, args.port)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'HSJA fictício: {url} | Ctrl+C para encerrar', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
