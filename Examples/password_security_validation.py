"""Valida cofres DPAPI e recuperação numa instância descartável do NexusDB (Windows)."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request
from oficina_mecanica_example.secure_store import save_json, load_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=Path(__file__).resolve().parents[1]/'target/debug/nexusdb.exe')
    parser.add_argument('--output', type=Path, default=Path('password-security-output'))
    args = parser.parse_args()
    binary = args.server.resolve(strict=True)
    root = args.output.resolve()/f'run-{time.time_ns()}'
    root.mkdir(parents=True)
    password = secrets.token_urlsafe(32)
    bootstrap, pepper = root/'bootstrap.dpapi', root/'pepper.dpapi'
    save_json(bootstrap, {'NEXUSDB_ADMIN_PASSWORD': password})
    save_json(pepper, {'active': 'v1', 'keys': {'v1': secrets.token_hex(32)}})
    report = {'status': 'running', 'checks': [], 'limitations': [
        'Dados e credenciais descartáveis; não homologa segurança de produção.',
        'Teste Windows DPAPI CurrentUser e CPU; não configura TLS, MFA ou KMS.']}
    def check(name, condition):
        report['checks'].append({'name': name, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(name)
        print('OK:', name, flush=True)
    check('Cofre descriptografado pela identidade atual', load_json(bootstrap)['NEXUSDB_ADMIN_PASSWORD'] == password)
    check('Senha ausente do arquivo cifrado', password.encode() not in bootstrap.read_bytes())
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('NEXUSDB_'):
            del env[key]
    env.update(NEXUSDB_DATA_ROOT=str(root/'data'), NEXUSDB_HTTP_ADDR=f'127.0.0.1:{port}',
               NEXUSDB_SECRETS_DPAPI_FILE=str(bootstrap), NEXUSDB_PASSWORD_PEPPER_FILE=str(pepper),
               NEXUSDB_MODE='SINGLE', NEXUSDB_CUDA_ENABLED='false', NEXUSDB_COMPUTE_BACKEND='CPU_SERIAL')
    def request(path, payload=None, user='admin', secret=None):
        headers = {'Content-Type': 'application/json', 'X-Database': 'EXAMPLE_AUTH_SECURITY'}
        if user:
            headers.update({'X-User': user, 'X-Pass': password if secret is None else secret})
        req = urllib.request.Request(f'http://127.0.0.1:{port}'+path,
            data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    process = None
    try:
        with (root/'server.log').open('w', encoding='utf8') as log:
            process = subprocess.Popen([str(binary)], cwd=root, env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError('Servidor encerrou; consulte server.log')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise TimeoutError('Servidor não iniciou')
            check('Rust usa senha e pepper DPAPI sem senha no ambiente', request('/db/admin/auth/status')[0] == 200)
            check('Database isolado criado', request('/db/admin/database/create', {'database': 'EXAMPLE_AUTH_SECURITY'})[0] == 200)
            reader_password = secrets.token_urlsafe(32)
            check('Conta criada com política nova', request('/db/admin/user/create', {
                'username': 'security_reader', 'password': reader_password, 'role': 'user'})[0] == 200)
            status, issued = request('/db/admin/password/reset-token', {'username': 'security_reader', 'ttl_seconds': 60})
            check('Administrador emite token temporário', status == 200 and bool(issued.get('reset_token')))
            new_password = secrets.token_urlsafe(32)
            reset = {'reset_token': issued['reset_token'], 'new_password': new_password}
            check('Recuperação por token sem senha anterior', request('/db/auth/password/reset', reset, user=None)[0] == 200)
            check('Token consumido não pode ser reutilizado', request('/db/auth/password/reset', reset, user=None)[0] == 400)
            report['auth_resources'] = request('/db/admin/auth/status')[1]
            check('Senhas e token ausentes do log', all(value not in (root/'server.log').read_text(encoding='utf8', errors='replace')
                for value in [password, reader_password, new_password, issued['reset_token']]))
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['error_type'] = type(error).__name__
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        (root/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        print('Relatório:', root/'report.json')


if __name__ == '__main__':
    main()
