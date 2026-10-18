"""Valida gateway Axum e NexusDB reais, em processos/diretórios isolados."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.request
import urllib.error
from crypto_temporal_lab import NexusSession, REPO
from nexusdb_ai.gateway_adapter import GatewayTransport, PublishedGatewayAdapter

DB = 'EXAMPLE_REST_GATEWAY'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=REPO/'target'/'debug'/'nexusdb.exe')
    parser.add_argument('--gateway', type=Path, default=REPO/'crates'/'nexusdb-rest-gateway'/'target'/'debug'/'nexusdb-rest-gateway.exe')
    parser.add_argument('--output', type=Path, default=Path('rest-gateway-output'))
    args = parser.parse_args(); binary=args.server.resolve(strict=True); gateway_binary=args.gateway.resolve(strict=True)
    root = args.output.resolve()/f'run-{time.time_ns()}'; root.mkdir(parents=True)
    session = NexusSession(binary, root, database=DB); process=None; log=None; checks=[]; details=[]; trace=[]; previous_check=time.perf_counter(); previous_request=0
    def check(label, condition):
        nonlocal previous_check, previous_request
        at=time.perf_counter();details.append({'name':label,'passed':bool(condition),'verification_span_ms':(at-previous_check)*1000,'evidence_request_ids':[r['id'] for r in trace[previous_request:]]});previous_check=at;previous_request=len(trace)
        partial={'database':DB,'verified':len(checks)+(1 if condition else 0),'status':'running' if condition else 'failed','results':details,'request_trace':trace}
        (root/'report.json').write_text(json.dumps(partial,ensure_ascii=False,indent=2),encoding='utf8')
        if not condition: raise AssertionError(label)
        checks.append(label); print(f'{len(checks)}. {label}', flush=True)
    try:
        password=secrets.token_urlsafe(32)
        session.request('/db/admin/user/create',{'username':'rest_reader','password':password,'role':'user','expires_days':0})
        session.request('/db/admin/grant',{'username':'rest_reader','database':DB,'access':'READ'})
        session.request('/db/admin/database/create',{'database':'EXAMPLE_REST_DENIED'})
        phronesis_db='EXAMPLE_REST_PHRONESIS'
        session.request('/db/admin/database/create',{'database':phronesis_db})
        session.request('/db/admin/grant',{'username':'rest_reader','database':phronesis_db,'access':'READ'})
        session.database=phronesis_db
        try:session.call('knowledge.initialize',{})
        finally:session.database=DB

        session.request('/db/admin/database/create',{'database':'EXAMPLE_REST_RATE'})
        session.request('/db/admin/grant',{'username':'rest_reader','database':'EXAMPLE_REST_RATE','access':'READ'})
        created=session.request('/db/data/node/bulk',{'rows':[{'key':str(i),'label':'Leito','properties':{'name':f'Bed {i}','sector':'A' if i<3 else 'B','ocupado':False,'higienizado':True,'manutencao':False,'secret':'DO-NOT-EXPOSE'}} for i in range(6)]})
        native=session.request('/db/data/node/search',{'label':'Leito','limit':10},user='rest_reader',password=password)
        check('Consulta de nós funciona com READ sem WRITE', len(native['rows'])==6)
        try:session.request('/db/data/node/create',{'label':'Leito','properties':{}},user='rest_reader',password=password)
        except RuntimeError as error:check('Conta READ não pode gravar nós', 'HTTP 403' in str(error))
        else:raise AssertionError('WRITE concedido indevidamente')
        ids=[row['id'] for row in native['rows']]
        session.request('/db/data/relationship/bulk',{'rows':[{'key':str(i),'from':ids[i],'to':ids[i+1],'type':'CONNECTED','properties':{'cost':1,'secret':'EDGE-SECRET'}} for i in range(5)]})
        base={'database':DB,'user_env':'DEMO_READER','password_env':'DEMO_PASSWORD','max_rows':10}
        node_op={'kind':'nodes','label':'Leito','properties':['name','sector','ocupado','higienizado','manutencao']}
        endpoints={
            'beds': base|{'params':{'sector':{'kind':'string','required':True,'values':['A','B']}},'operation':node_op|{'filter_params':{'sector':'sector'}}},
            'all-beds':base|{'operation':node_op},
            'clipped':base|{'max_rows':2,'operation':node_op},
            'edges':base|{'params':{'from':{'kind':'integer','required':True,'min':0}},'operation':{'kind':'relationships','relationship_type':'CONNECTED','properties':['cost']}},
            'query':base|{'params':{'sector':{'kind':'string','required':True}},'operation':{'kind':'query','query':'MATCH (n:Leito) WHERE n.sector=$sector RETURN n','columns':{'name':'/n/properties/name'}}},
            'rank':base|{'operation':{'kind':'call','procedure':'graph.projectPageRank','args':{'iterations':20},'columns':{'node_id':'/node_id','rank':'/page_rank'}}},
            'mcda':base|{'database':phronesis_db,'params':{'evaluation':{'kind':'object','required':True,'max_length':4}},'operation':{'kind':'call','procedure':'phronesis.evaluate','columns':{'ranking':'/eligible_alternatives','blocked':'/blocked_alternatives'}}},
            'denied':base|{'database':'EXAMPLE_REST_DENIED','operation':node_op},
            'future':base|{'not_before_ms':int(time.time()*1000)+300000,'operation':node_op},
            'disabled':base|{'enabled':False,'operation':node_op},
            'rate':base|{'database':'EXAMPLE_REST_RATE','operation':node_op},
            'expired':base|{'expires_at_ms':int(time.time()*1000)-1000,'operation':node_op},
            'locked':base|{'locked_params':{'sector':'A'},'operation':{'kind':'query','query':'MATCH (n:Leito) WHERE n.sector=$sector RETURN n','columns':{'name':'/n/properties/name'}}},
            'query-comment':base|{'params':{'sector':{'kind':'string','required':True}},'operation':{'kind':'query','query':'MATCH (n:Leito) WHERE n.sector=$sector RETURN n // published query','columns':{'name':'/n/properties/name'}}},
        }
        config=root/'endpoints.json';config.write_text(json.dumps({'endpoints':endpoints,'database_limits':{'EXAMPLE_REST_RATE':{'max_inflight':1,'requests_per_minute':1}}}),encoding='utf8')
        with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        url=f'http://127.0.0.1:{port}'; admin=secrets.token_urlsafe(32)
        env=os.environ|{'NEXUSDB_GATEWAY_CONFIG':str(config),'NEXUSDB_GATEWAY_STATE':str(root/'control.sqlite'),'NEXUSDB_GATEWAY_BIND':f'127.0.0.1:{port}','NEXUSDB_GATEWAY_ADMIN_KEY':admin,'NEXUSDB_BASE_URL':session.url,'DEMO_READER':'rest_reader','DEMO_PASSWORD':password}
        log=(root/'gateway.log').open('w',encoding='utf8')
        def launch():
            process=subprocess.Popen([str(gateway_binary)],cwd=root,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            for _ in range(200):
                if process.poll() is not None: raise RuntimeError('Gateway não iniciou; veja gateway.log')
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):return process
                except OSError:time.sleep(.05)
            process.terminate();process.wait(timeout=15);raise TimeoutError('Gateway readiness')
        process=launch()
        def request(path, payload=None, key=None, bearer=False, admin_access=False):
            headers={'Content-Type':'application/json'}
            if admin_access:headers['X-Gateway-Admin-Key']=admin
            elif key: headers['Authorization' if bearer else 'X-API-Key']=('Bearer '+key) if bearer else key
            req=urllib.request.Request(url+path,None if payload is None else json.dumps(payload).encode(),headers=headers)
            started=time.perf_counter()
            try:
                with urllib.request.urlopen(req,timeout=40) as response:result=(response.status,json.load(response),response.headers)
            except urllib.error.HTTPError as error:result=(error.code,json.load(error),error.headers)
            row={'id':len(trace)+1,'path':path,'method':req.get_method(),'http_status':result[0],'elapsed_ms':(time.perf_counter()-started)*1000,'request_id':result[1].get('meta',{}).get('request_id'),'error_code':result[1].get('error',{}).get('code'),'response_sha256':hashlib.sha256(json.dumps(result[1],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'row_count':result[1].get('meta',{}).get('row_count'),'response_fields':sorted(result[1])}
            trace.append(row)
            with (root/'request-evidence.jsonl').open('a',encoding='utf8') as evidence:evidence.write(json.dumps(row)+'\n')
            return result
        def issue(endpoint,ttl=3600,**extra):
            status,value,_=request('/admin/endpoints/'+endpoint+'/keys',{'ttl_seconds':ttl,**extra},admin_access=True)
            if status!=200:raise AssertionError(value)
            return value
        keys={name:issue(name) for name in endpoints}
        def call(name,params=None,bearer=False):return request('/v1/endpoints/'+name,{'params':params or {}},keys[name]['api_key'],bearer)
        status,value,h=call('beds',{'sector':'A'})
        check('X-API-Key consulta a rota real, com filtro e database fixo',status==200 and len(value['rows'])==3)
        check('Propriedades não publicadas não vazam', 'DO-NOT-EXPOSE' not in json.dumps(value) and 'secret' not in json.dumps(value))
        check('Resposta tem colunas, metadados e no-store',bool(value['columns']) and value['meta']['request_id'] and h['Cache-Control']=='no-store')
        check('Bearer é alias da chave no gateway',call('beds',{'sector':'B'},True)[0]==200)
        check('Chave de um endpoint não abre outro',request('/v1/endpoints/all-beds',{'params':{}},keys['beds']['api_key'])[0]==401)
        check('Sem chave e chave inválida são recusados',request('/v1/endpoints/beds',{'params':{}})[0]==401 and request('/v1/endpoints/beds',{'params':{}},'invalid')[0]==401)
        for label,params in [('Parâmetro obrigatório',{}),('Parâmetro desconhecido',{'sector':'A','query':'DROP DATABASE'}),('Database não pode ser alterado',{'sector':'A','database':'system'}),('Tipo inválido',{'sector':1}),('Enum inválido',{'sector':'X'})]:
            check(label+' é rejeitado',call('beds',params)[0]==400)
        status,value,_=call('clipped');check('Limite de linhas é aplicado antes do retorno',status==200 and len(value['rows'])==2 and value['meta']['truncated'])
        status,value,_=call('edges',{'from':ids[0]});check('Arestas usam tipo e propriedades publicados',status==200 and value['rows'][0]['to']==ids[1] and 'EDGE-SECRET' not in json.dumps(value))
        status,value,_=call('query',{'sector':'A'});check('Consulta salva traduz parâmetros tipados e linhas nativas',status==200 and len(value['rows'])==3)
        status,value,_=call('query',{'sector':"A' RETURN n; DROP DATABASE system"});check('Texto de parâmetro não vira instrução',status==200 and value['rows']==[])
        status,value,_=call('locked');check('Parâmetro fixado pelo operador é aplicado',status==200 and len(value['rows'])==3)
        check('Cliente não pode substituir parâmetro fixado',call('locked',{'sector':'B'})[0]==400)
        status,value,_=call('query-comment',{'sector':'A'});check('Comentário não remove o LIMIT interno',status==200 and len(value['rows'])==3)
        status,value,_=call('rank');check('PageRank é executado pelo CSR/runtime nativo',status==200 and len(value['rows'])==6 and value['meta']['native']['snapshot_version'] is not None)
        evaluation={'weights':{'quality':1.},'alternatives':[{'id':'A','scores':{'quality':.8}},{'id':'B','scores':{'quality':1.},'constraints':[{'id':'permission','satisfied':False}]}]}
        status,value,_=call('mcda',{'evaluation':evaluation});check('Phronesis nativo mantém restrições rígidas',status==200 and value['rows'][0]['ranking'][0]['id']=='A' and value['rows'][0]['blocked'][0]['id']=='B')
        check('Chave não supera RBAC do NexusDB',call('denied')[0]==403)
        check('Endpoint desativado e ainda não válido bloqueiam dados',call('disabled')[0]==403 and call('future')[0]==403)
        check('Prazo do próprio endpoint bloqueia todas as chaves',call('expired')[1]['error']['code']=='ENDPOINT_EXPIRED')
        short=issue('all-beds',ttl=1)
        # Deterministic wait until the server's returned deadline, not a timing assertion.
        remaining=(short['expires_at_ms']-int(time.time()*1000))/1000
        if remaining>0:time.sleep(remaining+.05)
        check('Duração da chave expira e bloqueia dados',request('/v1/endpoints/all-beds',{},short['api_key'])[1]['error']['code']=='API_KEY_EXPIRED')
        delayed=issue('all-beds',not_before_ms=int(time.time()*1000)+300000)
        check('Chave agendada não antecipa acesso',request('/v1/endpoints/all-beds',{},delayed['api_key'])[1]['error']['code']=='API_KEY_NOT_YET_VALID')
        def toggle(scope,identity,enabled):
            status,_,_=request('/admin/access',{'scope':scope,'id':identity,'enabled':enabled},admin_access=True);assert status==200
        toggle('key',short['key_id'],False);toggle('key',short['key_id'],True)
        check('Reativar chave expirada não renova o prazo',request('/v1/endpoints/all-beds',{},short['api_key'])[1]['error']['code']=='API_KEY_EXPIRED')
        for scope,identity in [('endpoint','all-beds'),('database',DB),('global','*')]:
            toggle(scope,identity,False);check('Bloqueio imediato por '+scope,call('all-beds')[0]==403)
            toggle(scope,identity,True);check('Reativação por '+scope,call('all-beds')[0]==200)
        toggle('key',keys['all-beds']['key_id'],False)
        check('Revogação individual bloqueia a chave',call('all-beds')[1]['error']['code']=='API_KEY_REVOKED')
        process.terminate();process.wait(timeout=15);process=launch()
        check('Revogação persiste após reiniciar gateway',call('all-beds')[1]['error']['code']=='API_KEY_REVOKED')
        toggle('key',keys['all-beds']['key_id'],True)
        check('Reativação não modifica prazo de validade',call('all-beds')[0]==200)
        status,value,_=request('/admin/state',admin_access=True)
        check('Estado administrativo não revela chaves nem senhas',status==200 and all(k['api_key'] not in json.dumps(value) for k in keys.values()) and password not in json.dumps(value))
        check('Chave de dados não concede administração',request('/admin/state',key=keys['beds']['api_key'])[0]==401)
        status,schema,_=request('/openapi.json',admin_access=True)
        check('OpenAPI administrativo contém perfis sem consultas e credenciais',status==200 and schema['openapi']=='3.1.0' and 'MATCH (' not in json.dumps(schema) and password not in json.dumps(schema))
        status,schema,_=request('/v1/endpoints/beds/openapi.json',key=keys['beds']['api_key'])
        check('OpenAPI da chave revela somente seu endpoint',status==200 and list(schema['paths'])==['/v1/endpoints/beds'])
        check('OpenAPI global não é público',request('/openapi.json')[0]==401)
        status,audit,_=request('/admin/audit',admin_access=True)
        records=audit['records']
        check('Auditoria estruturada registra sucesso e recusa',status==200 and any(r['status']==200 for r in records) and any(r['status']==401 for r in records) and all('duration_ms' in r and 'database' in r and 'user' in r for r in records))
        check('Auditoria não contém token, senha nem corpo da consulta',password not in json.dumps(audit) and admin not in json.dumps(audit) and all(k['api_key'] not in json.dumps(audit) for k in keys.values()))
        check('Limite de requisições permite a primeira chamada',call('rate')[0]==200)
        check('Limite de requisições recusa excesso por chave',call('rate')[1]['error']['code']=='RATE_LIMIT')
        adapter=PublishedGatewayAdapter(GatewayTransport(url,{name:k['api_key'] for name,k in keys.items()}),'all-beds','edges',{'pagerank':'rank'},'mcda')
        check('Pacote AI do ZIP lê nós pela API publicada',len(adapter.nodes('Leito'))==6)
        check('Pacote AI do ZIP lê vizinhos autorizados',adapter.neighbors(str(ids[0]))[0][1].id==str(ids[1]))
        check('Pacote AI delega PageRank e MCDA ao NexusDB',len(adapter.algorithm('pagerank')['rows'])==6 and adapter.evaluate(evaluation)['rows'][0]['ranking'][0]['id']=='A')
        process.terminate();process.wait(timeout=15)
        endpoints['clipped']['operation'] = endpoints['clipped']['operation'] | {'properties':node_op['properties']+['secret']}
        config.write_text(json.dumps({'endpoints':endpoints,'database_limits':{'EXAMPLE_REST_RATE':{'max_inflight':1,'requests_per_minute':1}}}),encoding='utf8');process=launch()
        status,value,_=call('clipped')
        check('Alterar o perfil não amplia acesso de chaves antigas',status==403 and value['error']['code']=='API_KEY_PROFILE_CHANGED')
        report={'database':DB,'verified':len(checks),'status':'passed','checks':checks,'results':details,'request_trace':trace,'limitations':['Dados simulados','TLS externo necessário para clientes remotos','Cancelamento HTTP não implica cancelamento do cálculo nativo','Sem benchmark de desempenho/CUDA real']}
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(f"{len(checks)} verificações passaram. Relatório: {root/'report.json'}")
    finally:
        if process is not None and process.poll() is None:process.terminate();process.wait(timeout=15)
        if log:log.close()
        session.close()

if __name__=='__main__':main()
