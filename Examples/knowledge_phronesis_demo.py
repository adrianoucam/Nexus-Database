"""Testes didáticos reais: Cortex/Phronesis sobre Python padrão + NexusDB.

Cria servidor, banco e usuários isolados com dados fictícios. Não executa decisões.
Requer compilação com --features phronesis,datalog,embedded.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
import secrets
import time
from crypto_temporal_lab import NexusSession, REPO

DB = 'EXAMPLE_KNOWLEDGE_PHRONESIS'


def evaluation():
    return {'weights': {'safety': .7, 'efficiency': .3}, 'alternatives': [
        {'id': 'A', 'scores': {'safety': .9, 'efficiency': .4}, 'intervals': {'safety': [.85, .95]}},
        {'id': 'B', 'scores': {'safety': .65, 'efficiency': .85}},
        {'id': 'BLOCKED', 'scores': {'safety': 1., 'efficiency': 1.}, 'constraints': [{'id': 'authorization', 'satisfied': False}]}],
        'sensitivity': [{'safety': .2, 'efficiency': .8}]}


def memory(text, **extra):
    return {'content': text, 'origin': {'kind': 'document', 'id': 'SIM-DOC', 'version': 'v1'}, 'valid_from': 0, **extra}


def validate(session, output):
    tests = []; timings = []; credentials = {}
    def check(label, condition):
        if not condition: raise AssertionError(label)
        tests.append(label); print(f'{len(tests)}. {label}')
    def call(name, arguments, user='admin'):
        started = time.perf_counter()
        value = session.request('/db/data/cypher', {'include_statement_results': True,
            'statements': [{'query': 'CALL '+name+'($request)', 'parameters': {'request': arguments}}]},
            user=user, password=credentials.get(user))
        timings.append({'operation': name, 'elapsed_ms': (time.perf_counter()-started)*1000})
        return value['statement_results'][0]
    def single(name, arguments, user='admin'): return call(name, arguments, user)['resultados'][0]
    def fails(label, callback, expected):
        try: callback()
        except RuntimeError as error: check(label, expected in str(error))
        else: raise AssertionError(label+' deveria falhar')
    auth_env = os.environ.copy(); auth_env.update(NEXUSDB_URL=session.url, NEXUSDB_USER='admin', NEXUSDB_PASSWORD=session.password, NEXUSDB_DATABASE=DB, PYTHONIOENCODING='utf-8')
    auth = subprocess.run([sys.executable, str(REPO/'examples'/'authentication_test.py')], env=auth_env, capture_output=True, text=True, encoding='utf8', timeout=60)
    check('Autenticação real: senha correta, senha inválida e Bearer não suportado', auth.returncode == 0)
    call('knowledge.initialize', {})
    check('Política por database ativada explicitamente', True)
    for user in ('sim_alice', 'sim_bob'):
        credentials[user] = secrets.token_urlsafe(24)
        session.request('/db/admin/user/create', {'username': user, 'password': credentials[user], 'role': 'user', 'expires_days': 0})
        for access in ('READ', 'WRITE'):
            session.request('/db/admin/grant', {'username': user, 'database': DB, 'access': access})
    alice = memory('AÇÃO: redefinir senha do projeto', idempotency_key='sim-A', embedding={'model_id': 'SIM-2D', 'values': [1., 0.]})
    first = call('memory.remember', alice, 'sim_alice'); alice_id = first['node_id']
    check('Memória, origem e commit durável', first['grade'] == 'asserted' and first['commit']['tx_id'] > 0)
    check('Repetição idempotente não duplica', call('memory.remember', alice, 'sim_alice')['deduplicated'])
    fails('Mesma chave com conteúdo diferente é rejeitada', lambda: call('memory.remember', alice | {'content': 'outro'}, 'sim_alice'), 'IDEMPOTENCY_CONFLICT')
    call('memory.remember', memory('senha: segredo fictício de Bob'), 'sim_bob')
    lexical = call('knowledge.search', {'query': 'acao senha'}, 'sim_alice')
    check('BM25 em português e ACL antes do ranking', lexical['processados'] == 1 and lexical['resultados'][0]['node_id'] == alice_id and 'Bob' not in json.dumps(lexical))
    check('Termos de consulta são deduplicados', call('knowledge.search', {'query': 'acao senha senha'}, 'sim_alice')['resultados'] == lexical['resultados'])
    check('Sem embeddings não inventa sinônimos', call('knowledge.search', {'query': 'recuperar credenciais'}, 'sim_alice')['processados'] == 0)
    check('Outro usuário não recebe a memória de Alice', call('knowledge.search', {'query': 'acao'}, 'sim_bob')['processados'] == 0)
    fails('Raw Cypher não contorna escopos', lambda: session.request('/db/data/cypher', {'statements': [{'query': 'MATCH (n) RETURN n'}]}, user='sim_bob', password=credentials['sim_bob']), 'KNOWLEDGE_SCOPED_DATABASE')
    fails('Busca nativa de nós não contorna escopos', lambda: session.request('/db/data/node/search', {'label': 'KnowledgeMemory'}, user='sim_bob', password=credentials['sim_bob']), 'KNOWLEDGE_SCOPED_DATABASE')
    fails('Ator não pode ser passado nos argumentos', lambda: call('memory.remember', alice | {'actor': 'sim_bob'}, 'sim_alice'), 'unknown field')
    fails('Retração exige acesso à memória', lambda: call('memory.retract', {'node_id': alice_id, 'expected_revision': 0, 'reason': 'não é minha'}, 'sim_bob'), 'REFERENCE_UNAVAILABLE')
    embedding = {'model_id': 'SIM-2D', 'values': [1., 0.]}
    hybrid = call('knowledge.hybridSearch', {'query': 'senha', 'embedding': embedding}, 'sim_alice')
    check('RRF combina scores por ID e snapshot', set(hybrid['resultados'][0]['contributions']) == {'lexical', 'vector_exact'})
    dbsf = call('knowledge.hybridSearch', {'query': 'senha', 'embedding': embedding, 'method': 'dbsf'}, 'sim_alice')
    check('DBSF explicita normalização de scores constantes', dbsf['resultados'][0]['score'] == 1.)
    check('Modelos diferentes não são comparados', 'vector_exact' not in call('knowledge.hybridSearch', {'query': 'senha', 'embedding': {'model_id': 'OTHER', 'values': [1., 0.]}}, 'sim_alice')['resultados'][0]['contributions'])
    fails('Dimensão incompatível é rejeitada', lambda: call('knowledge.hybridSearch', {'embedding': {'model_id': 'SIM-2D', 'values': [1., 0., 0.]}}, 'sim_alice'), 'dimension')
    check('Context pack respeita orçamento de caracteres', call('knowledge.contextPack', {'query': 'senha', 'max_chars': 1}, 'sim_alice')['processados'] == 0)
    for operation in ('memory.reflect', 'memory.consolidate'):
        check(operation+' propõe sem persistir inferência', not single(operation, {'query': 'senha'}, 'sim_alice')['persisted'])
    history = call('graph.historyStatus', {})['resultados'][0]['stamp']['recorded_at']
    replaced = call('memory.supersede', {'node_id': alice_id, 'expected_revision': 0, 'replacement': memory('Ação: senha substituída')}, 'sim_alice')
    check('Memória substituída sai da busca corrente', call('knowledge.search', {'query': 'senha'}, 'sim_alice')['resultados'][0]['node_id'] == replaced['node_id'])
    check('Memória anterior permanece historicamente consultável', call('knowledge.search', {'query': 'senha', 'context': {'projection': {'system_at': history}}}, 'sim_alice')['resultados'][0]['node_id'] == alice_id)
    call('memory.forget', {'node_id': replaced['node_id'], 'expected_revision': 0, 'reason': 'retirada simulada'}, 'sim_alice')
    check('Forget é retração auditável, sem apagar histórico', call('knowledge.search', {'query': 'senha'}, 'sim_alice')['processados'] == 0)
    initial_interval = call('memory.remember', memory('timeline original', valid_to=30), 'sim_alice')['node_id']
    middle = call('memory.supersede', {'node_id': initial_interval, 'expected_revision': 0, 'replacement': memory('timeline corrected', valid_from=10, valid_to=20)}, 'sim_alice')['node_id']
    for instant, expected in [(5, initial_interval), (15, middle), (25, initial_interval)]:
        interval = call('knowledge.search', {'query': 'timeline', 'context': {'projection': {'node_temporal': {'kind': 'at', 'timestamp': instant}}}}, 'sim_alice')
        check(f'Correção parcial preserva intervalos fora da substituição (t={instant})', interval['processados'] == 1 and interval['resultados'][0]['node_id'] == expected)
    evidence = call('knowledge.remember', memory('Fonte simulada: capacidade e autorização'))['node_id']
    promoted = call('memory.remember', memory('Síntese com evidência', evidence_ids=[evidence]))['node_id']
    check('Promoção mantém grade asserted', call('memory.promote', {'node_id': promoted, 'expected_revision': 0, 'reason': 'promover com origem'})['grade'] == 'asserted')
    for assigned in ('A', 'B'):
        call('knowledge.assertClaim', memory('Afirmação conflitante', evidence_ids=[evidence], claim={'subject': 'SIM-CASE', 'predicate': 'assigned', 'object': assigned, 'functional': True}))
    check('Afirmações funcionais conflitantes são indeterminate', single('knowledge.verifyClaim', {'subject': 'SIM-CASE', 'predicate': 'assigned', 'object': 'A'})['state'] == 'indeterminate')
    check('Ausência de afirmação não significa falsidade', single('knowledge.verifyClaim', {'subject': 'SIM-CASE', 'predicate': 'unknown', 'object': 'A'})['state'] == 'absent')
    nonfunctional = call('knowledge.assertClaim', memory('Afirmação multivalorada', claim={'subject': 'SIM-CASE', 'predicate': 'tag', 'object': 'A'}))
    check('Afirmação correspondente retorna supported', single('knowledge.verifyClaim', {'subject': 'SIM-CASE', 'predicate': 'tag', 'object': 'A'})['state'] == 'supported')
    check('Valor diferente multivalorado não é contradição', single('knowledge.verifyClaim', {'subject': 'SIM-CASE', 'predicate': 'tag', 'object': 'B'})['state'] == 'absent')
    arguments = [call('memory.remember', memory('Argumento '+letter))['node_id'] for letter in ('A', 'B', 'C')]
    grounded_request = {'arguments': [{'node_id': node} for node in arguments], 'attacks': [[arguments[2], arguments[1]], [arguments[1], arguments[0]]]}
    grounded = single('phronesis.grounded', grounded_request)
    check('Grounded: cadeia de ataques', grounded['accepted'] == [arguments[0], arguments[2]])
    cycle = single('phronesis.grounded', {'arguments': [{'node_id': node} for node in arguments[:2]], 'attacks': [[arguments[0], arguments[1]], [arguments[1], arguments[0]]]})
    check('Grounded: ciclo indecidido', cycle['undecided'] == arguments[:2])
    check('Grounded determinístico por ordem de inserção', single('phronesis.grounded', grounded_request | {'arguments': list(reversed(grounded_request['arguments']))}) == grounded)
    evaluated = single('phronesis.evaluate', {'evaluation': evaluation()})
    check('MCDA favorece A sob pesos declarados', evaluated['eligible_alternatives'][0]['id'] == 'A')
    check('Restrição rígida não é compensada por escore', evaluated['blocked_alternatives'][0]['id'] == 'BLOCKED')
    check('Sensibilidade detecta inversão de ranking', evaluated['sensitivity'][0]['rank_reversal'])
    check('Pareto e intervalo de estimativa são expostos', evaluated['pareto'] == ['A', 'B'] and evaluated['eligible_alternatives'][0]['score_interval'][0] < evaluated['eligible_alternatives'][0]['score'])
    invalid = evaluation(); invalid['weights']['safety'] = -.7
    fails('Pesos negativos são rejeitados', lambda: call('phronesis.evaluate', {'evaluation': invalid}), 'MCDA_INVALID_WEIGHTS')
    run = single('phronesis.create', {'situation': 'Comparação fictícia de alternativas', 'domain': 'didactic', 'evaluation': evaluation(), 'evidence_ids': [evidence], 'policy_version': 'SIM-POLICY-1', 'model_version': 'MCDA-1', 'reviewers': ['admin'], 'idempotency_key': 'SIM-DECISION'})
    decision = run['node_id']; revision = 0
    fails('Não permite pular revisão', lambda: call('phronesis.transition', {'node_id': decision, 'expected_revision': 0, 'to': 'APPROVED', 'reason': 'pular'}), 'INVALID_STATE_TRANSITION')
    for state in ('EVIDENCE_GATHERED', 'ALTERNATIVES_EVALUATED', 'HUMAN_REVIEW'):
        revision = single('phronesis.transition', {'node_id': decision, 'expected_revision': revision, 'to': state, 'reason': 'teste simulado'})['revision']
    fails('Aprovação exige atestado explícito do revisor', lambda: call('phronesis.transition', {'node_id': decision, 'expected_revision': revision, 'to': 'APPROVED', 'reason': 'sem atestado'}), 'HUMAN_REVIEW_REQUIRED')
    approve = {'node_id': decision, 'expected_revision': revision, 'to': 'APPROVED', 'reason': 'simulação', 'review_attestation': 'Revisão humana apenas simulada neste teste, sem ação real', 'idempotency_key': 'SIM-APPROVAL', 'selected_alternative': 'A'}
    fails('Restrição impede aprovar alternativa bloqueada', lambda: call('phronesis.transition', approve | {'selected_alternative': 'BLOCKED'}), 'ALTERNATIVE_BLOCKED_OR_UNKNOWN')
    revision = single('phronesis.transition', approve)['revision']
    check('Retry da aprovação é idempotente', single('phronesis.transition', approve)['deduplicated'])
    fails('Revisão otimista rejeita concorrência obsoleta', lambda: call('phronesis.transition', {'node_id': decision, 'expected_revision': 0, 'to': 'EXECUTED', 'reason': 'obsoleto'}), 'REVISION_CONFLICT')
    for state, extra in [('EXECUTED', {'execution_receipt': 'SIM-ONLY-NO-ACTION'}), ('OUTCOME_RECORDED', {'outcome': {'source_id': 'SIM-OUTCOME', 'observed': 'dado fictício'}}), ('REVIEWED', {})]:
        revision = single('phronesis.transition', {'node_id': decision, 'expected_revision': revision, 'to': state, 'reason': 'transição simulada', **extra})['revision']
    replay = single('phronesis.replay', {'node_id': decision})
    check('Replay reproduz a avaliação persistida', replay['replay_match'] and replay['state'] == 'REVIEWED')
    check('Histórico decisório contém oito eventos', len(replay['events']) == 8)
    check('Eventos decisórios têm timestamps do journal', all(isinstance(event['recorded_at'], int) for event in replay['events']))
    outcome_ids = [event['event_id'] for event in replay['events'] if event['to'] == 'OUTCOME_RECORDED']
    case = memory('Caso fictício: autorização e capacidade com desfecho observado', kind='case', case={'domain': 'didactic', 'situation': 'Comparação fictícia', 'decision_id': decision, 'outcome_event_ids': outcome_ids}, geometry={'type': 'Point', 'coordinates': [-46.6333, -23.5505], 'srid': 4326})
    case_id = call('memory.remember', case)['node_id']
    recalled = call('phronesis.cases', {'query': 'caso autorização'})
    check('Casos recuperados vinculam decisão e desfecho observados', recalled['processados'] == 1 and recalled['resultados'][0]['node_id'] == case_id)
    fails('Caso não aceita um evento que não é desfecho', lambda: call('memory.remember', case | {'case': case['case'] | {'outcome_event_ids': [replay['events'][0]['event_id']]}}), 'INVALID_OUTCOME_EVENT')
    located = call('knowledge.search', {'query': 'caso', 'context': {'projection': {'spatial': {'kind': 'radius', 'longitude': -46.6333, 'latitude': -23.5505, 'radius_m': 100}}}})
    check('Busca de conhecimento compõe filtro espacial nativo', located['processados'] == 1 and located['resultados'][0]['node_id'] == case_id)
    far = call('knowledge.search', {'query': 'caso', 'context': {'projection': {'spatial': {'kind': 'radius', 'longitude': 0., 'latitude': 0., 'radius_m': 100}}}})
    check('Filtro espacial exclui memória fora do raio', far['processados'] == 0)
    env = os.environ.copy(); env.update(NEXUSDB_MCP_URL=session.url, NEXUSDB_MCP_USER='admin', NEXUSDB_MCP_PASSWORD=session.password, NEXUSDB_MCP_DATABASE=DB)
    messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'knowledge_search', 'arguments': {'query': 'caso'}}}, {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'phronesis.transition', 'arguments': {}}}]
    before_mcp = call('graph.changeFeed', {})['cursor']
    bridge = subprocess.run([sys.executable, str(REPO/'examples'/'knowledge_mcp.py')], input=''.join(json.dumps(message)+'\n' for message in messages), text=True, encoding='utf8', capture_output=True, env=env, timeout=60, check=True)
    responses = [json.loads(line) for line in bridge.stdout.splitlines()]
    check('MCP stdio inicia e anuncia somente ferramentas de leitura', responses[0]['result']['protocolVersion'] == '2025-06-18' and all(tool['annotations']['readOnlyHint'] for tool in responses[1]['result']['tools']))
    check('MCP consulta o mesmo banco autenticado', responses[2]['result']['structuredContent']['processados'] == 1)
    check('MCP rejeita escrita e não altera o journal', 'error' in responses[3] and call('graph.changeFeed', before_mcp)['processados'] == 0)
    session.request('/db/data/relationship/bulk' , {'rows': [{'key': 'SIM-EDGE', 'from': arguments[0], 'to': arguments[1], 'type': 'EDGE', 'properties': {}}]})
    ppr = call('graph.ppr', {'seeds': [arguments[0]], 'max_iterations': 1000, 'tolerance': 1e-10})
    check('PPR conserva massa com vértices sem saída', abs(ppr['mass']-1.) < 1e-9 and ppr['converged'])
    check('Lane de grafo participa da recuperação híbrida', any('graph_ppr' in row['contributions'] for row in call('knowledge.hybridSearch', {'query': 'argumento', 'seeds': [arguments[0]]})['resultados']))
    check('Esquema observado separado de ontologia', single('graph.schema', {})['observed_schema'])
    check('Saúde explicita a semântica de multigrafo', 'multigraph' in single('graph.health', {})['semantics'])
    check('Valores de propriedades respeitam escopo', call('graph.propertyValues', {'label': 'KnowledgeMemory', 'key': 'text'})['cardinality'] > 0)
    feed = call('graph.changeFeed', {'limit': 1000})
    check('Feed só contém transações confirmadas', all(event['recorded_at'] is not None for event in feed['resultados']))
    check('Cursor de feed evita duplicação no próximo lote', call('graph.changeFeed', feed['cursor'])['processados'] == 0)
    fails('Feed bruto exige admin', lambda: call('graph.changeFeed', {}, 'sim_alice'), 'CHANGEFEED_REQUIRES_ADMIN')
    fails('Cursor de outra época é rejeitado', lambda: call('graph.changeFeed', {'epoch': 'wrong', 'after_sequence': 1}), 'EPOCH_MISMATCH')
    window = call('graph.window', {'rows': [{'id': 3, 'group': 'A', 'time': 2, 'value': None}, {'id': 1, 'group': 'A', 'time': 1, 'value': 2}, {'id': 2, 'group': 'A', 'time': 2, 'value': 4}], 'partition_key': 'group', 'order_key': 'time', 'value_key': 'value', 'row_key': 'id'})
    check('Janelas: COUNT/SUM/MIN/MAX/AVG/ROW_NUMBER/RANK', window['resultados'][0]['sum'] == 6 and window['resultados'][0]['avg'] == 3 and window['resultados'][2]['rank'] == 2)
    variable = lambda name: {'kind': 'variable', 'name': name}
    rules = [{'head': {'predicate': 'reachable', 'terms': [variable('x'), variable('y')]}, 'body': [{'predicate': 'edge', 'terms': [variable('x'), variable('y')]}]}]
    datalog = call('datalog.evaluate', {'rules': rules, 'predicate': 'reachable'})
    check('Datalog lê o mesmo grafo autorizado', datalog['resultados'][0]['tuple'] == arguments[:2])
    unsafe = json.loads(json.dumps(rules)); unsafe[0]['head']['terms'][0] = variable('unbound')
    fails('Datalog rejeita variável não ligada', lambda: call('datalog.evaluate', {'rules': unsafe, 'predicate': 'reachable'}), 'UNSAFE_RULE')
    call('knowledge.retract', {'node_id': evidence, 'expected_revision': 0, 'reason': 'fonte retirada'})
    check('Replay redige evidência retirada', single('phronesis.explain', {'node_id': decision})['redacted'])
    check('Caso não é recuperado após retirada da fonte', call('phronesis.cases', {'query': 'caso'})['processados'] == 0)
    check('Memória derivada de evidência retirada sai do contexto', call('knowledge.search', {'query': 'síntese'})['processados'] == 0)
    health = {'nodes': single('graph.schema', {})['nodes']}
    report = {'database': DB, 'verified': len(tests), 'checks': tests, 'durations': timings, 'evaluation': evaluated,
              'replay_before_retraction': replay, 'ppr': ppr, 'health': health,
              'limitations': ['Dados simulados; sem validade clínica ou jurídica', 'Scores não são probabilidades',
                 'Revisão humana é uma declaração do chamador autorizado; a API não identifica humanos',
                 'Nenhuma ação externa foi executada', 'IDs e metadados de commits são do database; isolamento de tráfego exige databases distintos']}
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=REPO/'target'/'debug'/'nexusdb.exe')
    parser.add_argument('--output', type=Path, default=Path('knowledge-python-output'))
    args = parser.parse_args(); binary = args.server.resolve(strict=True)
    output = args.output.resolve()/f'run-{time.time_ns()}'; output.mkdir(parents=True)
    session = NexusSession(binary, output, database=DB)
    try:
        report = validate(session, output)
        print(f"{report['verified']} verificações passaram. Relatório: {output/'report.json'}")
    finally: session.close()


if __name__ == '__main__': main()
