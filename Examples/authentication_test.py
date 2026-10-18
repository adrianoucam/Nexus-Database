"""Testa a autenticação atual, sem escrever dados ou imprimir credenciais.

NEXUSDB_URL, NEXUSDB_USER, NEXUSDB_PASSWORD, NEXUSDB_DATABASE.
NEXUSDB_API_TOKEN é testado como Bearer: servidor atual deve rejeitar.
"""
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request


def main():
    url = os.environ.get('NEXUSDB_URL', 'http://127.0.0.1:7474').rstrip('/')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise SystemExit('NEXUSDB_URL deve conter apenas a origem HTTP/HTTPS')
    if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise SystemExit('Conexão remota exige HTTPS')
    user = os.environ.get('NEXUSDB_USER', 'admin')
    password = os.environ.get('NEXUSDB_PASSWORD', '')
    database = os.environ.get('NEXUSDB_DATABASE', 'neo4j')
    if not password: raise SystemExit('Configure NEXUSDB_PASSWORD com a senha atual do usuário')
    body = json.dumps({'statements': [{'query': 'RETURN 1 AS teste'}]}).encode('utf8')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl): return None
    def probe(headers):
        request = urllib.request.Request(url+'/db/data/cypher', body, headers={'Content-Type': 'application/json', 'X-Database': database, **headers})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response: return response.status, json.load(response)
        except urllib.error.HTTPError as error: return error.code, {}
    status, value = probe({'X-User': user, 'X-Pass': password})
    if status != 200 or value.get('status') != 'success' or value.get('errors'):
        raise SystemExit(f'Credenciais/consulta não aceitas: HTTP {status}; verifique usuário, senha, database e READ')
    print('1. X-User/X-Pass autenticam e executam consulta de leitura')
    status, _ = probe({'X-User': user, 'X-Pass': secrets.token_urlsafe(32)})
    if status != 401: raise SystemExit(f'Senha inválida: esperado HTTP 401, recebido {status}')
    print('2. Senha inválida rejeitada com HTTP 401')
    status, _ = probe({'Authorization': 'Bearer '+os.environ.get('NEXUSDB_API_TOKEN', secrets.token_urlsafe(32))})
    if status != 401: raise SystemExit(f'Bearer isolado: esperado HTTP 401, recebido {status}')
    print('3. Bearer isolado rejeitado: NEXUSDB_API_TOKEN não é suportado')


if __name__ == '__main__': main()
