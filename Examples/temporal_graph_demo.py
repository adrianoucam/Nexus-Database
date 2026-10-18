"""Temporal graph demonstration inspired by the supplied Pometry proposal.

Starts ONLY its own NexusDB process, with synthetic data and a fresh data root.
Requires pyarrow; no Pometry service, LLM, production database or external UI.
"""
import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import random
import secrets
import socket
import subprocess
import time
import urllib.request
from arrow_client import batches

BASE = int(datetime(2026, 10, 1, 8, tzinfo=timezone.utc).timestamp() * 1000)
MINUTE = 60000
DB = 'EXAMPLE_TEMPORAL_PYTHON'
REPO_ROOT = Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description='Demonstração do grafo temporal NexusDB com dados simulados')
    parser.add_argument('--server',type=Path,default=REPO_ROOT / 'target' / 'debug' / ('nexusdb.exe' if os.name=='nt' else 'nexusdb'),
        help='Executável do servidor; padrão relativo ao repositório, não à pasta atual')
    parser.add_argument('--output',type=Path,default=Path('temporal-python-output'))
    parser.add_argument('--patients',type=int,default=50)
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    if not 2<=args.patients<=500:raise ValueError('patients deve ser 2..500')
    try:
        binary=args.server.resolve(strict=True)
    except (FileNotFoundError,NotADirectoryError):
        parser.error(f'Executável NexusDB não encontrado: {args.server.absolute()}. '
            f'Execute cargo build --bin nexusdb em {REPO_ROOT}, ou informe --server CAMINHO.')
    root=args.output.resolve()/('run-'+str(time.time_ns()));root.mkdir(parents=True,exist_ok=False)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    password=secrets.token_urlsafe(32);url=f'http://127.0.0.1:{port}'
    env=os.environ|{'NEXUSDB_DATA_ROOT':str(root/'data'),'NEXUSDB_HTTP_ADDR':f'127.0.0.1:{port}',
        'NEXUSDB_ADMIN_PASSWORD':password,'NEXUSDB_MODE':'SINGLE','NEXUSDB_CUDA_ENABLED':'false',
        'NEXUSDB_COMPUTE_BACKEND':'CPU_SERIAL','NEXUSDB_QUERY_CACHE':'false'}
    env.pop('NEXUSDB_TEMPORAL_HISTORY',None)
    report={'database':DB,'seed':args.seed,'patients':args.patients,'checks':[], 'steps':[],
        'concept':'Inspirado na proposta fornecida de grafos temporais da Pometry; implementação NexusDB.',
        'limitations':['CPU local; sem integração com Pometry/Raphtory.',
            'GraphRAG retorna evidências; não gera respostas por LLM.',
            'O exemplo não demonstra escala distribuída, GPU ou desempenho NVMe.']}
    def request(path,payload):
        req=urllib.request.Request(url+path,json.dumps(payload).encode(),headers={
            'Content-Type':'application/json','X-User':'admin','X-Pass':password,'X-Database':DB})
        with urllib.request.urlopen(req,timeout=60) as response:value=json.load(response)
        if value.get('errors') or value.get('status') in ('error','partial_error'):
            raise RuntimeError(str(value.get('errors',value.get('error'))))
        return value
    def query(text,parameters=None):
        return request('/db/data/cypher',{'statements':[{'query':text,'parameters':parameters or {}}]})
    def call(name,argument):return query('CALL '+name+'($request)',{'request':argument})
    def step(title,value):
        print(title,flush=True);report['steps'].append({'title':title,'result':value});return value
    def check(name,condition):
        if not condition:raise AssertionError(name)
        report['checks'].append(name)
    def create(label,props):return query('CREATE (n:'+label+' $props) RETURN id(n) AS id',{'props':props})['resultados'][0]['id']
    # Parameter binding replaces the map placeholder before parsing the node pattern.
    rng=random.Random(args.seed)
    with (root/'server.log').open('w',encoding='utf8') as log:
        process=subprocess.Popen([str(binary)],cwd=root,env=env,stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            for _ in range(200):
                if process.poll() is not None:raise RuntimeError('Servidor isolado falhou; veja server.log')
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.1)
            else:raise TimeoutError('Inicialização do servidor isolado')
            request('/db/admin/database/create',{'database':DB,'temporal_history':True})
            departments=[create('Department',{'name':name,'risk':5}) for name in ('Emergência','Enfermaria','UTI','Alta')]
            patient_risks=[2]+[rng.randrange(1,6) for _ in range(args.patients-1)]
            patients=[create('Patient',{'name':f'Paciente simulado {i+1}','risk':risk,'synthetic':True}) for i,risk in enumerate(patient_risks)]
            document=create('Document',{'name':'Registro simulado de admissão','embedding':[1.0,0.0,0.0],'synthetic':True})
            def transfer(a,b,start,end,duration):return {'from':departments[a],'to':departments[b],
                'type':'TRANSFER','properties':{'valid_from':BASE+start*MINUTE,'valid_to':BASE+end*MINUTE,
                    'duration_ms':duration*MINUTE,'layer':'transfer','source':'synthetic-schedule'}}
            transfers=[transfer(0,1,0,10,2),transfer(1,2,12,25,3),transfer(0,2,20,30,1),transfer(2,3,25,40,5)]
            rows=transfers+[{'from':p,'to':departments[1],'type':'OCCUPIES',
                'properties':{'valid_from':BASE,'valid_to':BASE+40*MINUTE,'layer':'care','source':'synthetic-admission'}} for p in patients]
            rows.append({'from':document,'to':patients[0],'type':'DESCRIBES','properties':{'layer':'evidence','source':'synthetic-document'}})
            request('/db/data/relationship/bulk',{'rows':rows})
            (root/'simulated_data.json').write_text(json.dumps({'departments':departments,'patients':patients,
                'document':document,'relationships':rows},indent=2,ensure_ascii=False),encoding='utf8')
            status=step('1. Histórico habilitado apenas no database de demonstração',call('graph.historyStatus',{}))['resultados'][0]
            old=status['stamp']['recorded_at']
            check('Histórico por database',status['temporal_history'] and status['scope']=='database')
            checkpoint=step('2. Checkpoint do estado original',call('graph.historyCheckpoint',{}))
            def project(spec):
                result=call('graph.project',{'projection':spec,'limit':1000})
                degree=call('graph.projectDegree',{'projection':spec,'limit':1000})
                # The HTTP batch envelope returns rows. In this loop-free fixture,
                # sum of undirected degrees / 2 counts its directed relationships.
                result['total_nodes']=len(result['resultados'])
                result['total_relationships']=sum(row['degree'] for row in degree['resultados'])//2
                return result
            at5=step('3. Visão pontual: transferências às 08:05 UTC',project({'system_at':old,'layers':['transfer'],
                'temporal':{'kind':'at','timestamp':BASE+5*MINUTE}}))
            check('Estado temporal original às 08:05',at5['total_relationships']==1)
            at10=project({'system_at':old,'layers':['transfer'],'temporal':{'kind':'at','timestamp':BASE+10*MINUTE}})
            check('Intervalos semiabertos: aresta encerrada às 08:10',at10['total_relationships']==0)
            window=step('4. Janela com composição de camada: transferências entre 08:00 e 08:15',project({
                'system_at':old,'layers':['transfer'],'temporal':{'kind':'window','start':BASE,'end':BASE+15*MINUTE,'mode':'any'}}))
            check('Janela por interseção',window['total_relationships']==2)
            whole=project({'system_at':old,'layers':['transfer'],'temporal':{'kind':'window','start':BASE+13*MINUTE,'end':BASE+14*MINUTE,'mode':'all'}})
            check('Janela por cobertura integral',whole['total_relationships']==1)
            filtered=step('5. Projeção por propriedade e camada de atendimento',project({'layers':['care'],
                'node_filters':[{'field':'risk','operator':'ge','value':4}]}))
            check('Propriedades compõem um subgrafo induzido',filtered['total_relationships']==sum(risk>=4 for risk in patient_risks))
            path_request={'source':departments[0],'target':departments[2],'departure':BASE,
                'projection':{'system_at':old,'layers':['transfer']}}
            earliest=step('6. Menor chegada: espera e sequência cronológica',call('graph.earliestArrival',path_request))['resultados'][0]['path']
            fewest=step('7. Menos saltos pode chegar mais tarde',call('graph.temporalBfs',path_request))['resultados'][0]['path']
            check('Chegada mínima em dois saltos às 08:15',earliest['found'] and earliest['arrival']==BASE+15*MINUTE and len(earliest['steps'])==2)
            check('BFS temporal em um salto às 08:21',fewest['found'] and fewest['arrival']==BASE+21*MINUTE and len(fewest['steps'])==1)
            correction=transfer(1,2,4,25,3)
            request('/db/data/relationship/upsert',correction)
            query('MATCH (n:Patient) WHERE id(n)=$id SET n.risk=5',{'id':patients[0]})
            query('MATCH (n:Patient) WHERE id(n)=$id DETACH DELETE n',{'id':patients[-1]})
            new=call('graph.historyStatus',{})['resultados'][0]['stamp']['recorded_at']
            corrected=step('8. Correção retroativa: validade às 08:04, registrada posteriormente',call('graph.earliestArrival',
                path_request|{'projection':{'system_at':new,'layers':['transfer']}}))['resultados'][0]['path']
            unchanged=call('graph.earliestArrival',path_request)['resultados'][0]['path']
            check('Novo estado chega às 08:07',corrected['arrival']==BASE+7*MINUTE)
            check('Histórico anterior mantém chegada às 08:15',unchanged['arrival']==earliest['arrival'])
            current=query('MATCH (n:Patient) RETURN count(n) AS count')['resultados'][0]['count']
            old_export=call('graph.exportArrow',{'export_id':'historical_patients','entity':'nodes','projection':{'system_at':old},
                'columns':[{'name':'risk','field':'risk','data_type':'int64'},{'name':'name','field':'name','data_type':'utf8'}],
                'batch_rows':16})
            arrow_rows=[]
            for batch in batches(url,DB,'admin',password,'historical_patients'):arrow_rows.extend(batch.to_pylist())
            check('Arrow recupera entidade excluída',current==args.patients-1 and any(row['id']==patients[-1] for row in arrow_rows))
            check('Arrow preserva propriedade histórica',next(row for row in arrow_rows if row['id']==patients[0])['risk']==2)
            step('9. Arrow histórico lido em Python pela API autenticada',{'export':old_export,'rows':len(arrow_rows),'sample':arrow_rows[:3]})
            events=step('10. Eventos de alteração rastreáveis',call('graph.historyEvents',{'entity':'nodes','id':patients[0],'limit':100}))['resultados'][0]['events']
            check('Eventos preservam criação e atualização',len(events)>=2)
            evidence=step('11. Temporal GraphRAG: documento e caminhos de evidência',call('graphRAG.temporalRetrieve',{
                'vector':[1,0,0],'seed_label':'Document','k':1,'depth':2,'max_nodes':20,'projection':{'system_at':old}}))['resultados'][0]
            check('GraphRAG retorna evidência histórica',any(node['id']==patients[0] for node in evidence['nodes']))
            degrees=step('12. Algoritmo sobre a visão reutilizável',call('graph.projectDegree',{
                'projection':{'system_at':old,'layers':['transfer']},'limit':10}))
            report.update(passed=True,system_at_original=old,system_at_current=new,arrow_rows=len(arrow_rows),
                earliest_minutes=15,bfs_minutes=21,corrected_minutes=7)
            (root/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
            render(root,transfers,correction,report)
        finally:
            process.terminate();process.wait(timeout=15)
    print(f'{len(report["checks"])} verificações passaram. Abra: {root / "temporal_graph.html"}')
    print('Relatório:',root/'report.json')

def render(root,transfers,correction,report):
    # All input to HTML is synthetic or escaped; JSON cannot terminate a script.
    payload=json.dumps({'original':transfers,'corrected':[transfers[0],correction,*transfers[2:]],
        'base':BASE,'minute':MINUTE},ensure_ascii=False).replace('<','\\u003c')
    rows=''.join('<li>'+html.escape(c)+'</li>' for c in report['checks'])
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>NexusDB — grafo temporal</title>
<style>body{font:17px system-ui;max-width:1050px;margin:40px auto;padding:20px;background:#101827;color:#eef3fa}section{background:#1c293e;padding:24px;margin:20px 0;border-radius:12px}svg{width:100%;height:210px}line{stroke-width:4}text{fill:#eef3fa}input{width:75%}select{font-size:17px}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #40506a}</style>
<h1>O grafo muda com o tempo</h1><p>Demonstração NexusDB com dados hospitalares simulados, inspirada na proposta fornecida da Pometry.</p>
<section><label>Estado conhecido pelo banco: <select id="version"><option value="original">Antes da correção</option><option value="corrected">Depois da correção</option></select></label>
<p>Tempo de validade: <strong id="clock"></strong></p><input id="time" type="range" min="0" max="40" value="5" step="1">
<svg viewBox="0 0 900 210"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#51d5bc"/></marker></defs>
<line id="edge0" x1="110" y1="80" x2="310" y2="80"/><line id="edge1" x1="350" y1="80" x2="550" y2="80"/><line id="edge2" x1="110" y1="135" x2="550" y2="135"/><line id="edge3" x1="610" y1="80" x2="790" y2="80"/>
<text x="30" y="45">Emergência</text><text x="270" y="45">Enfermaria</text><text x="550" y="45">UTI</text><text x="790" y="45">Alta</text></svg>
<p id="active"></p><p>Verde: relação válida neste minuto. Cinza: fora do intervalo [início, fim). A correção muda o começo de Enfermaria → UTI de 08:12 para 08:04; o histórico anterior continua consultável.</p></section>
<section><h2>Uma conexão estática não garante um caminho cronológico</h2><table><tr><th>Consulta</th><th>Resultado validado</th></tr><tr><td>Chegada mínima no estado original</td><td>08:15 UTC, dois saltos, com espera</td></tr><tr><td>BFS temporal: menos saltos</td><td>08:21 UTC, um salto</td></tr><tr><td>Chegada mínima após correção</td><td>08:07 UTC, dois saltos</td></tr></table></section>
<section><h2>Verificações executadas contra o banco</h2><ul>CHECKS</ul><p>O relatório JSON contém todas as respostas. A animação usa os mesmos intervalos simulados, sem manter o servidor em execução.</p></section>
<p>Também demonstrados: janela, camada, filtro de propriedades, checkpoint, exclusões históricas, Arrow e evidências GraphRAG. Execução CPU local; sem integração direta com Pometry, LLM ou benchmark NVMe.</p>
<script>const data=PAYLOAD;const time=document.getElementById('time'),version=document.getElementById('version');function update(){let n=Number(time.value),count=0;document.getElementById('clock').textContent='08:'+String(n).padStart(2,'0')+' UTC';data[version.value].forEach((e,i)=>{let p=e.properties,on=data.base+n*data.minute>=p.valid_from&&data.base+n*data.minute<p.valid_to;count+=on?1:0;let line=document.getElementById('edge'+i);line.style.stroke=on?'#51d5bc':'#46536a';line.style.opacity=on?1:.35;line.setAttribute('marker-end',on?'url(#arrow)':'');});document.getElementById('active').textContent=count+' transferência(s) válida(s).';}time.oninput=update;version.onchange=update;update();</script></html>'''
    (root/'temporal_graph.html').write_text(page.replace('CHECKS',rows).replace('PAYLOAD',payload),encoding='utf8')

if __name__=='__main__':main()
