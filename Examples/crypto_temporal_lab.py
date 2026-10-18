"""Laboratório didático: Python padrão + APIs reais do NexusDB.

Sem pandas, NetworkX, Streamlit, Arrow, navegador ou serviço externo.
Tkinter apresenta a tela; --headless executa a mesma análise sem interface.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import secrets
import socket
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request

HOUR = 3600000
MINUTE = 60000
BASE = int(datetime(2022, 5, 7, tzinfo=timezone.utc).timestamp() * 1000)
DB = 'EXAMPLE_CRYPTO_TEMPORAL'
REPO = Path(__file__).resolve().parent.parent
SCENARIOS = ('coordinated', 'independent', 'whale', 'synchronized_small')
FIELDS = ('event_id', 'timestamp', 'asset', 'from', 'to', 'trader', 'side', 'usd_cents', 'price_usd')
PAPER = 'https://arxiv.org/abs/2407.10614'


def utc(timestamp):
    return datetime.fromtimestamp(timestamp / 1000, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def synthetic(seed=42, scenario='coordinated'):
    rng = random.Random(seed)
    events = []
    def add(hour, minute, asset, actor, cents, side):
        pool = 'POOL_' + asset
        price = (1.0 if hour < 8 else [0.92, 0.70, 0.40, 0.15][hour-8]) if asset == 'UST' else 1.0
        events.append({'event_id': 'SIM-' + str(len(events)+1), 'timestamp_ms': BASE+hour*HOUR+minute*MINUTE,
            'asset': asset, 'from': actor if side == 'SELL' else pool,
            'to': pool if side == 'SELL' else actor, 'trader': actor, 'side': side,
            'usd_cents': cents, 'price_usd': price})
    for hour in range(12):
        for asset in ('UST', 'USDC', 'DAI'):
            # Partially overlapping layers, then six wallets move from UST to
            # USDC after the synthetic shock. This is injected, not inferred causality.
            traders=range(6,24) if asset=='USDC' and hour<10 else range(12,24) if asset=='DAI' else range(6,24) if asset=='UST' and hour>=10 else range(24)
            for trader in traders:
                add(hour, rng.randrange(60), asset, f'W{trader:02d}', rng.randrange(10000, 30001), rng.choice(('BUY','SELL')))
        if hour in (8,9):
            if scenario == 'whale':
                for minute in range(24): add(hour,minute,'UST','W00',1000000,'SELL')
            else:
                for trader in range(6):
                    for minute in (10,20,30,40):
                        add(hour, rng.randrange(60) if scenario == 'independent' else minute,
                            'UST', f'W{trader:02d}', 1000 if scenario == 'synchronized_small' else 1000000, 'SELL')
    return sorted(events, key=lambda e:(e['timestamp_ms'],e['event_id']))


def write_csv(path, events):
    with path.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        for event in events:
            writer.writerow({**{k:event[k] for k in FIELDS if k!='timestamp'},'timestamp':utc(event['timestamp_ms'])})


def read_csv(path):
    events=[];ids=set()
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not set(FIELDS[:-1]).issubset(reader.fieldnames or []):
            raise ValueError('CSV exige colunas: '+', '.join(FIELDS[:-1]))
        for line,row in enumerate(reader,2):
            if len(events)>=5000:raise ValueError('Limite didático: 5000 eventos por execução')
            try:
                timestamp=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
                if timestamp.tzinfo is None:raise ValueError('timestamp deve incluir fuso UTC/offset')
                if timestamp.microsecond%1000:raise ValueError('timestamp deve ter precisão máxima de milissegundos')
                cents=int(row['usd_cents']);price=float(row['price_usd']) if row.get('price_usd') else None
                if cents<=0 or cents>10**14 or price is not None and (not math.isfinite(price) or price<=0):raise ValueError('valor/preço inválido')
                strings={k:row[k].strip() for k in ('event_id','asset','from','to','trader','side')}
                if any(not v or len(v)>160 for v in strings.values()):raise ValueError('campo textual vazio/grande')
                if strings['event_id'] in ids:raise ValueError('event_id duplicado; não duplicar pernas da negociação')
                if strings['side'] not in ('BUY','SELL') or strings['trader'] not in (strings['from'],strings['to']):raise ValueError('trader deve ser endpoint e side BUY/SELL')
                if strings['from']==strings['to']:raise ValueError('transferência para si mesmo não é uma negociação neste modelo')
                ids.add(strings['event_id'])
                delta=timestamp.astimezone(timezone.utc)-datetime(1970,1,1,tzinfo=timezone.utc)
                millis=(delta.days*86400+delta.seconds)*1000+delta.microseconds//1000
                events.append(strings|{'timestamp_ms':millis,'usd_cents':cents,'price_usd':price})
            except (ValueError,KeyError) as error:raise ValueError(f'CSV linha {line}: {error}') from error
    if not events:raise ValueError('CSV vazio')
    return sorted(events,key=lambda e:(e['timestamp_ms'],e['event_id']))


def cosine_sync(vectors):
    normalized=[]
    for vector in vectors:
        norm=math.sqrt(sum(x*x for x in vector))
        if norm:normalized.append([x/norm for x in vector])
    pairs=list(itertools.combinations(normalized,2))
    return sum(sum(a*b for a,b in zip(x,y)) for x,y in pairs)/len(pairs) if pairs else 0.0


def metrics(events,start,end,seed=42,permutations=199):
    """Volume por trader/negociação; pools não são contados como traders.

    O teste desloca circularmente os histogramas de cada trader: preserva
    contagem/padrão intratrader e rompe alinhamento entre traders. É exploratório.
    """
    volumes=Counter();histograms=defaultdict(lambda:[0]*60);sales=0;prices=defaultdict(list)
    by_asset=defaultdict(set)
    for event in events:
        actor=event['trader'];volumes[actor]+=event['usd_cents'];by_asset[event['asset']].add(actor)
        bin_index=min(59,max(0,int((event['timestamp_ms']-start)*60/(end-start))))
        histograms[actor][bin_index]+=1
        sales+=event['usd_cents']*(1 if event['side']=='SELL' else -1)
        if event.get('price_usd') is not None:prices[event['asset']].append(event['price_usd'])
    total=sum(volumes.values());ranked=sorted(volumes,key=lambda k:(-volumes[k],k));top=ranked[:6]
    shares=[volumes[k]/total for k in ranked] if total else []
    hhi=sum(p*p for p in shares);entropy=-sum(p*math.log(p) for p in shares)
    selected=[volumes[k] for k in top];mean=sum(selected)/len(selected) if selected else 0
    cv=math.sqrt(sum((x-mean)**2 for x in selected)/len(selected))/mean if mean else 0
    vectors=[histograms[k] for k in top];sync=cosine_sync(vectors)
    enough=len(top)==6 and all(sum(v)>=3 for v in vectors)
    p_value=None;null_mean=None
    if enough and permutations:
        key=json.dumps([start,end,sorted(volumes),seed],sort_keys=True).encode()
        rng=random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8],'big'))
        null=[]
        for _ in range(permutations):
            shifted=[]
            for vector in vectors:
                offset=rng.randrange(60);shifted.append(vector[offset:]+vector[:offset])
            null.append(cosine_sync(shifted))
        p_value=(1+sum(x>=sync-1e-12 for x in null))/(permutations+1)
        null_mean=sum(null)/len(null)
    top6=sum(volumes[k] for k in top)/total if total else 0
    concentrated=top6>=.80 and hhi>=.10 and total>0
    # Numerical tolerance at the inclusive boundary (e.g. exact 4/5 cosine).
    aligned=enough and sync>=.80-1e-12 and p_value is not None and p_value<=.05
    candidate=concentrated and aligned and cv<=.15
    overlaps=[]
    for a,b in itertools.combinations(sorted(by_asset),2):
        union=by_asset[a]|by_asset[b];overlaps.append({'assets':[a,b],'jaccard':len(by_asset[a]&by_asset[b])/len(union) if union else 0})
    return {'events':len(events),'active_traders':len(volumes),'volume_usd_cents':total,
        'net_sell_usd_cents':sales,'hhi':hhi,'entropy':entropy,'effective_traders':1/hhi if hhi else 0,
        'top1_share':shares[0] if shares else 0,'top6_share':top6,'top6_cv':cv,'synchrony':sync,
        'synchrony_null_mean':null_mean,'p_exploratory':p_value,'permutations':permutations if enough else 0,
        'enough_observations':enough,'concentrated':concentrated,'synchronized':aligned,'candidate':candidate,
        'ranking':[{'trader':k,'usd_cents':volumes[k],'share':volumes[k]/total,'trades':sum(histograms[k])} for k in ranked],
        'layer_overlap':overlaps,'median_price_usd':{asset:statistics.median(values) for asset,values in prices.items()}}


class NexusSession:
    def __init__(self,binary,root,database=DB,environment=None):
        self.database=database
        self.root=root;self.process=None;self.trace=[]
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        self.url=f'http://127.0.0.1:{self.port}';self.password=secrets.token_urlsafe(32)
        self.log=(root/'server.log').open('w',encoding='utf8')
        env=os.environ|{'NEXUSDB_DATA_ROOT':str(root/'data'),'NEXUSDB_HTTP_ADDR':f'127.0.0.1:{self.port}',
            'NEXUSDB_ADMIN_PASSWORD':self.password,'NEXUSDB_MODE':'SINGLE','NEXUSDB_CUDA_ENABLED':'false',
            'NEXUSDB_COMPUTE_BACKEND':'CPU_SERIAL','NEXUSDB_QUERY_CACHE':'false'}
        env.update(environment or {})
        try:
            self.process=subprocess.Popen([str(binary)],cwd=root,env=env,stdout=self.log,stderr=self.log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            for _ in range(200):
                if self.process.poll() is not None:raise RuntimeError('NexusDB não iniciou; veja server.log')
                try:
                    with socket.create_connection(('127.0.0.1',self.port),timeout=.1):break
                except OSError:time.sleep(.1)
            else:raise TimeoutError('Inicialização NexusDB')
            self.request('/db/admin/database/create',{'database':self.database,'temporal_history':True})
        except BaseException:self.close();raise
    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate();self.process.wait(timeout=15)
        self.log.close()
    def request(self,path,payload,*,user='admin',password=None):
        req=urllib.request.Request(self.url+path,json.dumps(payload).encode(),headers={
            'Content-Type':'application/json','X-User':user,'X-Pass':self.password if password is None else password,'X-Database':self.database})
        try:
            with urllib.request.urlopen(req,timeout=60) as response:value=json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'HTTP {error.code} em {path}: {error.read(4096).decode("utf8",errors="replace")}') from error
        if value.get('errors') or value.get('status') in ('error','partial_error'):
            raise RuntimeError(str(value.get('errors',value.get('error'))))
        return value
    def call(self,name,args):
        self.trace.append({'procedure':name,'arguments':args})
        value=self.request('/db/data/cypher',{'include_statement_results':True,'statements':[{'query':'CALL '+name+'($request)','parameters':{'request':args}}]})
        if name.startswith(('spatial.', 'knowledge.', 'memory.', 'phronesis.', 'datalog.')) or name in ('graph.project','graph.projectDegree','graph.projectPageRank','graph.ppr','graph.schema','graph.health','graph.changeFeed','graph.window'):
            return value.get('statement_results',value['resultados'])[0]
        return value['resultados'][0]

    def load(self,events):
        addresses=sorted({e[k] for e in events for k in ('from','to')});actors={e['trader'] for e in events}
        if len(addresses)>100:raise ValueError('Limite didático: 100 endpoints')
        self.ids={};self.names={};self.assets=sorted({e['asset'] for e in events})
        if len(self.assets)>6:raise ValueError('Limite didático: 6 mercados')
        result=self.request('/db/data/node/bulk',{'rows':[{'key':key,'label':'Wallet',
            'properties':{'address':key,'role':'trader' if key in actors else 'counterparty'}} for key in addresses]})
        for row in result['resultados']:
            self.ids[row['key']]=row['id'];self.names[row['id']]=row['key']
        for offset in range(0,len(events),200):
            rows=[]
            for event in events[offset:offset+200]:
                props={k:v for k,v in event.items() if k not in ('from','to')}
                props.update(layer=event['asset'],valid_from=event['timestamp_ms'],valid_to=event['timestamp_ms']+1)
                rows.append({'key':event['event_id'],'from':self.ids[event['from']],
                    'to':self.ids[event['to']],'type':'TRADE','properties':props})
            self.request('/db/data/relationship/bulk',{'rows':rows})
        self.stamp=self.call('graph.historyStatus',{})['stamp']['recorded_at']
        self.checkpoint=self.call('graph.historyCheckpoint',{})
        self.system_at=self.stamp
    def fetch(self,start,end,assets):
        if not assets:return []
        response=self.call('graphRAG.temporalRetrieve',{'seeds':sorted(self.names),'depth':1,
            'max_nodes':100,'max_edges':10000,'projection':{'system_at':self.system_at,'layers':list(assets),
                'temporal':{'kind':'window','start':start,'end':end,'mode':'any'}}})
        if response['truncated']:raise RuntimeError('Resultado truncado; reduza os dados/janela. Não calcular métricas incompletas.')
        return [{'relationship_id':edge['id'],'from':self.names[edge['from']],'to':self.names[edge['to']],
            **edge['properties']} for edge in response['relationships']]


class Lab:
    def __init__(self,session,events,seed,root,scenario):
        self.session=session;self.seed=seed;self.root=root;self.scenario=scenario
        self._save_lock=threading.RLock()
        self.start=min(e['timestamp_ms'] for e in events)//HOUR*HOUR
        self.end=(max(e['timestamp_ms'] for e in events)//HOUR+1)*HOUR
        self.hours=(self.end-self.start)//HOUR
        if self.hours>168:raise ValueError('Limite didático: intervalo de 7 dias')
        print('Lendo eventos persistidos e filtrados pelo NexusDB...',flush=True)
        self.persisted=session.fetch(self.start,self.end,session.assets)
        if len(self.persisted)!=len(events):raise AssertionError('Importação/leitura perdeu eventos')
        if {e['event_id'] for e in self.persisted}!={e['event_id'] for e in events}:raise AssertionError('IDs de evento divergentes')
        compared=('timestamp_ms','usd_cents','asset','from','to','trader','side','price_usd')
        expected={e['event_id']:tuple(e[k] for k in compared) for e in events}
        if any(expected[e['event_id']]!=tuple(e[k] for k in compared) for e in self.persisted):raise AssertionError('Propriedades divergentes')
        self.timeline=[]
        for hour in range(self.hours):
            start=self.start+hour*HOUR;end=start+HOUR
            by_layer={}
            for asset in ['Todas',*session.assets]:
                selected=[e for e in self.persisted if start<=e['timestamp_ms']<end and (asset=='Todas' or e['asset']==asset)]
                by_layer[asset]=metrics(selected,start,end,seed)
            self.timeline.append(by_layer)
        self.report={'scenario':scenario,'synthetic':scenario!='CSV','seed':seed,'events':len(events),
            'database':DB,'system_at':session.stamp,'checkpoint':session.checkpoint,'source':PAPER,
            'timeline':self.timeline,'checks':['IDs/quantidades e propriedades conferidos após persistência'],
            'meaning':'Sinais exploratórios, sem atribuição de identidade, intenção, shorting ou causalidade.',
            'null_model':'Deslocamentos circulares independentes; sem correção de múltiplas comparações.'}
        self.report['layer_movements']=[]
        for hour in range(1,self.hours):
            previous=defaultdict(set);current=defaultdict(set)
            for e in self.persisted:
                if self.start+(hour-1)*HOUR<=e['timestamp_ms']<self.start+hour*HOUR:previous[e['asset']].add(e['trader'])
                if self.start+hour*HOUR<=e['timestamp_ms']<self.start+(hour+1)*HOUR:current[e['asset']].add(e['trader'])
            for source,target in itertools.permutations(session.assets,2):
                moved=(previous[source]-current[source])&(current[target]-previous[target])
                if moved:self.report['layer_movements'].append({'hour':hour,'from_layer':source,'to_layer':target,'wallets':sorted(moved)})
        self.save()
    def analyze(self,hour,width,assets):
        start=self.start+hour*HOUR;end=start+width*HOUR
        events=self.session.fetch(start,end,assets)
        result=metrics(events,start,end,self.seed)
        result.update(start=utc(start),end=utc(end),assets=assets,hour_index=hour,window_hours=width,system_at=self.session.system_at)
        self.report['last_selection']=result;self.save();return events,result
    def save(self):
        with self._save_lock:
            for name,value in [('report',self.report),('queries',self.session.trace)]:
                temporary=self.root/(name+'.json.tmp')
                temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')
                temporary.replace(self.root/(name+'.json'))
    def validate(self):
        if self.scenario=='CSV':
            asset=self.session.assets[0];fetched,result=self.analyze(0,1,[asset])
            oracle=[e for e in self.persisted if self.start<=e['timestamp_ms']<self.start+HOUR and e['asset']==asset]
            if {e['event_id'] for e in fetched}!={e['event_id'] for e in oracle}:raise AssertionError('Filtro CSV divergente')
            if result['volume_usd_cents']!=sum(e['usd_cents'] for e in oracle):raise AssertionError('Volume CSV divergente')
            self.report['checks']+=['Janela/camada CSV conferida','Volume CSV inteiro conferido']
            self.report.update(passed=True,validation_scope='Contrato de importação/consulta; sem verdade-terreno de coordenação')
            self.save();print('CSV validado: persistência, janela, camada e volume. Sem validação de intenção/coordenação.',flush=True)
            return
        baseline=self.timeline[0]['UST'];shock=self.timeline[8]['UST'];control=self.timeline[8]['USDC']
        if baseline['candidate'] or control['candidate']:raise AssertionError('Controle normal marcado como coordenação')
        if self.scenario=='coordinated' and not shock['candidate']:raise AssertionError('Sinal injetado não localizado')
        if self.scenario!='coordinated' and shock['candidate']:raise AssertionError('Controle alternativo marcado como coordenação')
        fetched,result=self.analyze(8,1,['UST'])
        oracle=[e for e in self.persisted if self.start+8*HOUR<=e['timestamp_ms']<self.start+9*HOUR and e['asset']=='UST']
        if {e['event_id'] for e in fetched}!={e['event_id'] for e in oracle}:raise AssertionError('Janela/camada divergente')
        if result['volume_usd_cents']!=sum(e['usd_cents'] for e in oracle):raise AssertionError('Volume divergente')
        self.report['checks']+=['Controle normal não sinalizado','Controle USDC não sinalizado',
            'Cenário corresponde ao sinal/controle injetado','Filtro temporal/camada conferido','Volume inteiro conferido']
        self.report['passed']=True;self.save()
        print('Validação passou:',self.scenario,'HHI=',round(shock['hhi'],3),
            'top6=',round(shock['top6_share'],3),'sincronismo=',round(shock['synchrony'],3),flush=True)


def money(cents):return f'US$ {cents/100:,.2f}'


def gui(lab,smoke=False):
    import tkinter as tk
    from tkinter import ttk, messagebox
    try:root=tk.Tk()
    except tk.TclError as error:raise RuntimeError('A interface exige Python com Tcl/Tk instalado. Use seu Python padrão (py), ou --headless para executar sem tela.') from error
    root.title('NexusDB · Laboratório de grafos temporais e mercados')
    root.geometry(f'{min(1350,root.winfo_screenwidth()-60)}x{min(880,root.winfo_screenheight()-100)}')
    if smoke:root.withdraw()
    root.columnconfigure(0,weight=1);root.rowconfigure(2,weight=1)
    ttk.Label(root,text='Quem concentra o volume? Quando? Em quais mercados?',font=('Segoe UI',18,'bold')).grid(row=0,column=0,sticky='w',padx=16,pady=8)
    ttk.Label(root,text='Dados '+('CSV fornecido' if lab.scenario=='CSV' else 'SIMULADOS · '+lab.scenario)+
        '  |  Carteira ≠ pessoa. Sinais de alinhamento não provam ataque, intenção ou causa.').grid(row=1,column=0,sticky='w',padx=16)
    panes=ttk.Panedwindow(root,orient='horizontal');panes.grid(row=2,column=0,sticky='nsew',padx=12,pady=8)
    left=ttk.Frame(panes);right=ttk.Frame(panes);panes.add(left,weight=3);panes.add(right,weight=2)
    left.columnconfigure(0,weight=1);left.rowconfigure(2,weight=1)
    controls=ttk.Frame(left);controls.grid(row=0,column=0,sticky='ew')
    hour=tk.IntVar(value=0);width=tk.IntVar(value=1);layers={a:tk.BooleanVar(value=True) for a in lab.session.assets}
    ttk.Label(controls,text='Janela começa na hora:').grid(row=0,column=0)
    slider=tk.Scale(controls,from_=0,to=lab.hours-1,orient='horizontal',variable=hour,length=280);slider.grid(row=0,column=1)
    ttk.Label(controls,text='Duração (horas):').grid(row=0,column=2)
    width_box=ttk.Combobox(controls,values=(1,2,4),textvariable=width,state='readonly',width=4);width_box.grid(row=0,column=3)
    for i,(asset,var) in enumerate(layers.items()):ttk.Checkbutton(controls,text=asset,variable=var,command=lambda:analyze()).grid(row=1,column=i)
    status=tk.StringVar(value='Pronto');ttk.Label(left,textvariable=status,wraplength=740).grid(row=1,column=0,sticky='w',pady=6)
    canvas=tk.Canvas(left,bg='#101b2d',height=420,highlightthickness=0);canvas.grid(row=2,column=0,sticky='nsew')
    chart=tk.Canvas(left,bg='#f7f9fc',height=145,highlightthickness=0);chart.grid(row=3,column=0,sticky='ew',pady=4)
    ttk.Label(left,text='Azul: participação top 6 · Dourado: preço UST (eixo direito) · Clique para selecionar uma hora.').grid(row=4,column=0,sticky='w')
    right.columnconfigure(0,weight=1);right.rowconfigure(3,weight=1)
    summary=tk.StringVar();ttk.Label(right,textvariable=summary,font=('Segoe UI',11),justify='left',wraplength=480).grid(row=0,column=0,sticky='ew',pady=4)
    ranking=ttk.Treeview(right,columns=('actor','share','volume','trades'),show='headings',height=7)
    for key,title,size in [('actor','Carteira',110),('share','Participação',95),('volume','Volume USD',115),('trades','Trades',55)]:ranking.heading(key,text=title);ranking.column(key,width=size)
    ranking.grid(row=1,column=0,sticky='ew')
    detail=tk.StringVar(value='Clique numa carteira ou ligação para ver os eventos persistidos.');ttk.Label(right,textvariable=detail,wraplength=480).grid(row=2,column=0,sticky='w',pady=6)
    evidence=ttk.Treeview(right,columns=('id','time','asset','actor','usd'),show='headings',height=12)
    for key,title,size in [('id','Evento',85),('time','UTC',105),('asset','Mercado',65),('actor','Trader',80),('usd','USD',105)]:evidence.heading(key,text=title);evidence.column(key,width=size)
    evidence.grid(row=3,column=0,sticky='nsew');scroll=ttk.Scrollbar(right,orient='vertical',command=evidence.yview);scroll.grid(row=3,column=1,sticky='ns');evidence.configure(yscrollcommand=scroll.set)
    state={'events':[],'metrics':{},'busy':False,'pending':False};executor=ThreadPoolExecutor(max_workers=1)
    palette={'UST':'#fa796f','USDC':'#69b2ff','DAI':'#6ee7b7'}
    for asset,color in zip([a for a in lab.session.assets if a not in palette],
            ('#c5a9f5','#ffbd69','#80ded9','#f59bd7','#c8dc82','#a8b8f8')):palette[asset]=color
    def show_events(events,label):
        detail.set(label+' · '+str(len(events))+' eventos (exibidos até 1000).')
        evidence.delete(*evidence.get_children())
        for e in sorted(events,key=lambda x:(x['timestamp_ms'],x['event_id']))[:1000]:
            evidence.insert('', 'end', iid=e['event_id'],values=(e['event_id'],utc(e['timestamp_ms'])[11:19],e['asset'],e['trader'],f"{e['usd_cents']/100:,.2f}"))
    def draw():
        canvas.delete('all');w=max(canvas.winfo_width(),600);h=max(canvas.winfo_height(),350)
        events=state['events'];m=state['metrics'];top={r['trader'] for r in m.get('ranking',[])[:6]}
        actors=sorted({e['trader'] for e in events});others=sorted({e[k] for e in events for k in ('from','to')}-set(actors))
        positions={}
        for i,a in enumerate(actors):
            angle=2*math.pi*i/max(1,len(actors));positions[a]=(w/2+math.cos(angle)*w*.38,h/2+math.sin(angle)*h*.36)
        for i,a in enumerate(others):positions[a]=(w/2+(i-(len(others)-1)/2)*85,h/2)
        aggregate=defaultdict(list)
        for e in events:aggregate[e['from'],e['to'],e['asset']].append(e)
        for (a,b,asset),rows in aggregate.items():
            x,y=positions[a];xx,yy=positions[b];total=sum(e['usd_cents'] for e in rows)
            tag='edge'+str(len(canvas.find_all()))
            canvas.create_line(x,y,xx,yy,fill=palette.get(asset,'#c5a9f5'),width=min(8,1+math.log10(max(1,total/100))),arrow=tk.LAST,tags=tag)
            canvas.tag_bind(tag,'<Button-1>',lambda event,rs=rows,a=a,b=b,asset=asset:show_events(rs,f'{a} → {b} · {asset}'))
        for a,(x,y) in positions.items():
            counterparty=a in others;r=18 if counterparty else 11
            color='#8ba1bf' if counterparty else '#fc837b' if a in top and m.get('candidate') else '#f5cf75' if a in top else '#d9e5f5'
            tag='wallet'+str(len(canvas.find_all()))
            canvas.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='#fff',tags=tag)
            canvas.create_text(x,y+r+10,text=a if len(a)<18 else a[:7]+'…'+a[-5:],fill='#eef4ff',font=('Segoe UI',8),tags=tag)
            canvas.tag_bind(tag,'<Button-1>',lambda event,a=a:show_events([e for e in state['events'] if a in (e['from'],e['to'])],a))
        canvas.create_text(12,14,anchor='nw',fill='#eef4ff',width=w-24,text='Seta = fluxo · Espessura = volume · Cor = mercado · Amarelo = top 6 · Vermelho = combinação sinalizada')
        if not events:canvas.create_text(w/2,h/2,text='Nenhum evento nesta janela/camada',fill='white')
        chart.delete('all');cw=max(chart.winfo_width(),600);points=[]
        active=m.get('assets',[a for a,var in layers.items() if var.get()]);key=active[0] if len(active)==1 else 'Todas'
        for i,entry in enumerate(lab.timeline):
            x=35+i*(cw-65)/max(1,lab.hours-1);y=115-entry[key]['top6_share']*85;points.extend((x,y))
            chart.create_text(x,133,text=str(i),font=('Segoe UI',8))
        chart.create_text(8,20,anchor='nw',text='100%');chart.create_text(8,115,anchor='nw',text='0%')
        if len(points)>2:chart.create_line(*points,fill='#2369c8',width=3)
        if 'UST' in active:
            price_values=[entry['UST']['median_price_usd'].get('UST') for entry in lab.timeline]
            maximum=max([v for v in price_values if v is not None]+[1.0]);price_points=[]
            for i,value in enumerate(price_values):
                if value is None:
                    if len(price_points)>2:chart.create_line(*price_points,fill='#b87913',width=2)
                    price_points=[];continue
                price_points.extend((35+i*(cw-65)/max(1,lab.hours-1),115-value/maximum*85))
            if len(price_points)>2:chart.create_line(*price_points,fill='#b87913',width=2)
            chart.create_text(cw-4,18,anchor='ne',text=f'US$ {maximum:g}',fill='#8a5910')
        selected_x=35+m.get('hour_index',hour.get())*(cw-65)/max(1,lab.hours-1);chart.create_line(selected_x,20,selected_x,120,fill='#d4483a',dash=(3,3))
    def apply(value):
        events,m=value;state.update(events=events,metrics=m,busy=False)
        p='amostra insuficiente' if m['p_exploratory'] is None else f"{m['p_exploratory']:.3f} (exploratório)"
        label='Concentração + alinhamento temporal: investigar' if m['candidate'] else 'Concentração sem combinação de coordenação' if m['concentrated'] else 'Sem combinação de sinais nesta seleção'
        prices=' · '.join(f'{a}: US$ {v:g}' for a,v in m['median_price_usd'].items()) or 'Não informado'
        overlaps=' · '.join('/'.join(o['assets'])+f": {o['jaccard']:.0%}" for o in m['layer_overlap']) or 'Selecione mais de um mercado'
        moved=[m for m in lab.report['layer_movements'] if m['hour']==state['metrics']['hour_index']]
        movement='; '.join(m['from_layer']+'→'+m['to_layer']+': '+str(len(m['wallets']))+' carteiras' for m in moved) or 'Sem mudança entre camadas nesta hora'
        summary.set(f"{label}\n{m['events']} negociações · {m['active_traders']} traders ativos\nVolume: {money(m['volume_usd_cents'])}\nTop 1: {m['top1_share']:.1%} · Top 6: {m['top6_share']:.1%}\nHHI: {m['hhi']:.3f} · Traders efetivos: {m['effective_traders']:.1f}\nCV dos top 6: {m['top6_cv']:.3f}\nSincronismo: {m['synchrony']:.3f} · p: {p}\nSaldo de vendas USD: {money(m['net_sell_usd_cents'])}\nPreços medianos: {prices}\nSobreposição de traders: {overlaps}\n{movement}")
        ranking.delete(*ranking.get_children())
        for r in m['ranking']:ranking.insert('','end',iid=r['trader'],values=(r['trader'],f"{r['share']:.1%}",f"{r['usd_cents']/100:,.2f}",r['trades']))
        status.set(m['start']+' até '+m['end']+' · Histórico system_at='+str(m['system_at']))
        show_events(events,'Janela completa');draw()
    def analyze():
        if state['busy']:state['pending']=True;return
        active=[a for a,v in layers.items() if v.get()]
        if not active:messagebox.showinfo('Mercado','Selecione ao menos um mercado.');return
        state['busy']=True;status.set('Consultando a janela/camadas no NexusDB…')
        future=executor.submit(lab.analyze,int(hour.get()),int(width.get()),active)
        def poll():
            if not future.done():root.after(80,poll);return
            try:apply(future.result())
            except Exception as error:state['busy']=False;status.set('Erro');messagebox.showerror('NexusDB',str(error))
            if state['pending']:state['pending']=False;root.after(0,analyze)
        root.after(80,poll)
    def preset(h,asset):
        hour.set(min(h,lab.hours-1));width.set(1)
        for a,v in layers.items():v.set(asset=='Todas' or a==asset)
        analyze()
    buttons=ttk.Frame(root);buttons.grid(row=3,column=0,sticky='ew',padx=16,pady=8)
    ttk.Button(buttons,text='Consultar janela no NexusDB',command=analyze).pack(side='left',padx=4)
    ttk.Button(buttons,text='1 · Mercado normal',command=lambda:preset(0,'UST' if 'UST' in layers else 'Todas')).pack(side='left',padx=4)
    ttk.Button(buttons,text='2 · Concentração simulada',command=lambda:preset(8,'UST'),state='disabled' if lab.scenario=='CSV' else 'normal').pack(side='left',padx=4)
    ttk.Button(buttons,text='3 · Comparar USDC',command=lambda:preset(8,'USDC'),state='disabled' if 'USDC' not in layers else 'normal').pack(side='left',padx=4)
    def explain():
        messagebox.showinfo('Como interpretar',
            'Cada relação representa UMA negociação, válida por 1 ms no seu timestamp.\n'
            'NexusDB seleciona a janela/camadas e preserva os dados; Python calcula indicadores.\n\n'
            'Participação = volume do trader / volume total. HHI = soma das participações ao quadrado.\n'
            'CV mede semelhança dos volumes dos seis maiores. Sincronismo compara seus histogramas em 60 subintervalos.\n'
            'O p exploratório vem de deslocamentos circulares independentes, com 199 permutações. Não há ajuste para múltiplas janelas.\n\n'
            'O sinal combina top6 ≥80%, HHI ≥0,10, CV ≤0,15, sincronismo ≥0,80, ≥3 operações/trader e p ≤0,05. Limiares didáticos.\n'
            'Bots, arbitragem, notícias e concentração em pools também podem explicar padrões. A tela não identifica pessoas nem comprova shorting ou ataque.\n\n'
            'Camadas não devem ser somadas se o CSV duplica as pernas da mesma negociação.')
    ttk.Button(buttons,text='Explicar indicadores',command=explain).pack(side='left',padx=4)
    ttk.Button(buttons,text='Salvar relatório',command=lambda:(lab.save(),messagebox.showinfo('Relatório',str(lab.root/'report.json')))).pack(side='left',padx=4)
    def chart_click(event):
        hour.set(max(0,min(lab.hours-1,round((event.x-35)*(lab.hours-1)/max(1,chart.winfo_width()-65)))));analyze()
    chart.bind('<Button-1>',chart_click)
    slider.bind('<ButtonRelease-1>',lambda event:analyze())
    width_box.bind('<<ComboboxSelected>>',lambda event:analyze())
    canvas.bind('<Configure>',lambda event:draw() if state['metrics'] else None)
    ranking.bind('<<TreeviewSelect>>',lambda event:show_events([e for e in state['events'] if e['trader']==ranking.selection()[0]],ranking.selection()[0]) if ranking.selection() else None)
    def event_details(event):
        if not evidence.selection():return
        identifier=evidence.selection()[0]
        row=next((e for e in state['events'] if e['event_id']==str(identifier)),None)
        if row:
            popup=tk.Toplevel(root);popup.title('Evidência persistida no NexusDB');text=tk.Text(popup,width=85,height=24)
            text.pack(fill='both',expand=True);text.insert('1.0',json.dumps({'system_at':lab.session.system_at,'event':row},indent=2,ensure_ascii=False));text.configure(state='disabled')
    evidence.bind('<Double-1>',event_details)
    def close():executor.shutdown(wait=True,cancel_futures=True);root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    if smoke:
        root.update_idletasks();apply(lab.analyze(min(8,lab.hours-1),1,['UST'] if 'UST' in layers else lab.session.assets))
        if not canvas.find_all() or not ranking.get_children():raise AssertionError('Interface não populada')
        show_events(state['events'][:2],'Teste de seleção');root.update_idletasks();close();print('GUI smoke: widgets, grafo, ranking e evidências preenchidos.',flush=True)
    else:root.after(150,analyze);root.mainloop()


def main():
    p=argparse.ArgumentParser(description='Laboratório didático de mercados com Python padrão e NexusDB')
    p.add_argument('--server',type=Path,default=REPO/'target'/'debug'/('nexusdb.exe' if os.name=='nt' else 'nexusdb'))
    p.add_argument('--output',type=Path,default=Path('crypto-temporal-output'));p.add_argument('--seed',type=int,default=42)
    p.add_argument('--scenario',choices=SCENARIOS,default='coordinated');p.add_argument('--csv',type=Path)
    p.add_argument('--headless',action='store_true');p.add_argument('--gui-smoke',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    try:binary=args.server.resolve(strict=True)
    except OSError:p.error(f'Executável ausente: {args.server}. Compile com cargo build --bin nexusdb em {REPO}.')
    try:events=read_csv(args.csv) if args.csv else synthetic(args.seed,args.scenario)
    except (ValueError,OSError) as error:p.error(str(error))
    # Reject oversized input before starting a database process.
    if len({e[k] for e in events for k in ('from','to')})>100:p.error('Limite: 100 endpoints')
    if len({e['asset'] for e in events})>6:p.error('Limite: 6 mercados')
    if max(e['timestamp_ms'] for e in events)-min(e['timestamp_ms'] for e in events)>167*HOUR:p.error('Limite: 7 dias')
    root=args.output.resolve()/('run-'+str(time.time_ns()));root.mkdir(parents=True,exist_ok=False)
    write_csv(root/'transactions.csv',events)
    session=None
    try:
        print('Iniciando NexusDB isolado e carregando',len(events),'negociações...',flush=True)
        session=NexusSession(binary,root);session.load(events)
        lab=Lab(session,events,args.seed,root,'CSV' if args.csv else args.scenario);lab.validate()
        print('Relatório:',root/'report.json',flush=True)
        if not args.headless:gui(lab,args.gui_smoke)
    except Exception as error:
        p.exit(1,f'Erro no laboratório: {error}\n')
    finally:
        if session:session.close()


if __name__=='__main__':main()
