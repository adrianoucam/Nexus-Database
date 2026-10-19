#!/usr/bin/env python3
"""Simulador integralmente ficticio para prototipos de grafos hospitalares. Apenas stdlib."""
import csv, random, math, sqlite3, json, zipfile, os, collections, heapq
from pathlib import Path
from datetime import datetime, timedelta
R=random.Random(20261008)
OUT=Path('/mnt/data/hsja_simulado');OUT.mkdir(exist_ok=True)
START=datetime(2026,10,1); END=datetime(2026,11,1)
rows={}
def add(table,**vals): rows.setdefault(table,[]).append(vals)
def dt(x):return x.strftime('%Y-%m-%d %H:%M:%S')
def randt(a,b):return a+timedelta(seconds=R.uniform(0,(b-a).total_seconds()))
def weighted(items, weights):return R.choices(items,weights,k=1)[0]
# dimencoes institucionais: somente referencia sintetica; departamentos e capacidade hipoteticos
units=[('UTI_ADULTO_II','UTI adulto tipo II',51,'UTI_ADULTO','CRITICO'),('UTI_ADULTO_III','UTI adulto tipo III',27,'UTI_ADULTO','CRITICO'),('UTI_NEONATAL','UTI neonatal',16,'UTI_NEONATAL','CRITICO'),('UTI_PEDIATRICA','UTI pediatrica',8,'UTI_PEDIATRICA','CRITICO'),('CIRURGICA','Internacao cirurgica',93,'CIRURGICO','INTERMEDIARIO'),('CLINICA','Internacao clinica',74,'CLINICO','INTERMEDIARIO'),('PEDIATRIA','Internacao pediatrica',25,'PEDIATRICO','INTERMEDIARIO'),('OBSTETRICIA','Internacao obstetrica',15,'OBSTETRICO','INTERMEDIARIO'),('ISOLAMENTO','Isolamento',1,'ISOLAMENTO','ESPECIAL')]
assert sum(u[2] for u in units)==310
for i,(id_,name,n,kind,level) in enumerate(units):add('unidades',unidade_id=id_,nome=name,tipo=kind,nivel_cuidado=level,capacidade_cadastrada=n,localizacao_ficticia=f'BLOCO_SIM_{1+i//3}')
for name,desc in [('EMERGENCIA_ADULTO','Pronto atendimento adulto'),('EMERGENCIA_PED','Pronto atendimento pediatrico'),('CENTRO_CIRURGICO','Centro cirurgico'),('IMAGEM','Diagnostico por imagem'),('ONCOLOGIA','Oncologia'),('AMBULATORIO','Ambulatorio'),('HEMODIALISE','Hemodialise'),('HOTELARIA','Hotelaria, transporte e higienizacao')]:add('unidades',unidade_id=name,nome=desc,tipo='SERVICO',nivel_cuidado='NA',capacidade_cadastrada=0,localizacao_ficticia='NA')
rooms={};beds={}; roomno=0
for uid,n,capacity,kind,level in units:
    remaining=capacity; b=0
    while remaining:
        roomno+=1;room_id=f'Q{roomno:04d}'
        n_beds=1 if 'UTI' in uid or kind in ('OBSTETRICO','ISOLAMENTO') else (2 if remaining>=2 and R.random()<0.63 else 1)
        n_beds=min(remaining,n_beds)
        accommodation='CTI' if 'UTI' in uid else ('PRIVATIVO' if n_beds==1 else 'COLETIVO')
        premium = int(uid in ['CLINICA','CIRURGICA'] and n_beds==1 and R.random()<0.12)
        add('quartos',quarto_id=room_id,unidade_id=uid,capacidade=n_beds,tipo_acomodacao='PREMIUM_SIMULADO' if premium else accommodation,andar_simulado='NAO_VERIFICADO',isolamento=int(kind=='ISOLAMENTO'),ala_simulada='ALA_SIM_'+uid)
        rooms[room_id]=(uid,n_beds)
        for _ in range(n_beds):
            b+=1;bed_id=f'L{len(beds)+1:04d}'
            beds[bed_id]={'unidade_id':uid,'quarto_id':room_id,'tipo':kind}
            add('leitos',leito_id=bed_id,quarto_id=room_id,unidade_id=uid,tipo=kind,ativo=1,ventilador=int('UTI' in uid and R.random()<0.86),monitor=int('UTI' in uid),suporte_isolamento=int(kind=='ISOLAMENTO'),modalidade='MISTO_SIMULADO')
        remaining-=n_beds
# colaboradores 1470 (hipotese de simulacao)
first=['Ana','Bruno','Carla','Diego','Elisa','Fabio','Gabriela','Henrique','Isabela','Joao','Larissa','Marcos','Natalia','Otavio','Paula','Rafael','Sofia','Tiago','Vanessa','Walter']
last=['Silva','Costa','Oliveira','Almeida','Ferreira','Santos','Pereira','Barbosa','Mendes','Martins','Gomes','Ribeiro','Lima','Teixeira','Moreira','Rocha']
prof_roles=[('MEDICO',210),('ENFERMEIRO',290),('TEC_ENFERMAGEM',630),('FISIOTERAPEUTA',65),('TECNICO_IMAGEM',35),('ANESTESISTA',45),('HIGIENIZACAO',90),('TRANSPORTE',35),('ADMINISTRATIVO',70)]
assert sum(x[1] for x in prof_roles)==1470
prof_by_role=collections.defaultdict(list); professionals={}
clinical_units=[x[0] for x in units]
for role,count in prof_roles:
 for j in range(count):
    pid=f'F{len(professionals)+1:05d}';home=weighted(clinical_units,[1.9,1.3,.65,.4,2.3,2.0,.8,.7,.15])
    if role=='TECNICO_IMAGEM':home='IMAGEM'
    if role=='ANESTESISTA':home='CENTRO_CIRURGICO'
    if role=='HIGIENIZACAO':home='HOTELARIA'
    speciality=weighted(['CLINICA','CIRURGIA','CARDIOLOGIA','NEUROLOGIA','PEDIATRIA','OBSTETRICIA','ONCOLOGIA','TERAPIA_INTENSIVA'],[25,18,12,8,10,8,8,11]) if role in ['MEDICO','ANESTESISTA'] else 'NA'
    add('profissionais',profissional_id=pid,nome_ficticio=f'{R.choice(first)} {R.choice(last)} SIM {pid}',categoria=role,especialidade= speciality,unidade_base=home,registro_profissional_ficticio=f'TESTE-{pid}',vinculo='SIMULADO')
    professionals[pid]=(role,home,speciality);prof_by_role[role].append(pid)
# escala: 12x36 aproximado em blocos alternados; campos permitem testes de cobertura
for pid,(role,home,spec) in professionals.items():
 if role in ['ADMINISTRATIVO']:
    shifts=[(d,8,16) for d in range(31) if (START+timedelta(days=d)).weekday()<5]
 else:
    parity=R.randrange(2); hour=R.choice([7,19])
    shifts=[(d,hour,hour+12) for d in range(31) if d%2==parity]
 for d,h1,h2 in shifts:
    start=START+timedelta(days=d,hours=h1);stop=START+timedelta(days=d,hours=h2)
    if start<END:
     add('escalas',escala_id=f'E{len(rows.get("escalas",[]))+1:07d}',profissional_id=pid,unidade_id=home,inicio=dt(start),fim=dt(stop),papel=role)
# pacientes completamente ficticios, identificadores sem CPF
N_PATIENTS=16000
for k in range(N_PATIENTS):
    p=f'P{k+1:06d}'; age=R.randint(0,93)
    add('pacientes',paciente_id=p,nome_ficticio=f'{R.choice(first)} {R.choice(last)} SIM {p}',idade_anos=age,sexo=R.choice('FM'),municipio_origem=weighted(['Itaperuna','Bom Jesus do Itabapoana','Santo Antonio de Padua','Miracema','Porciuncula','Outro municipio simulado'],[42,15,12,10,9,12]),identificador_externo='FICTICIO-'+p)
# encontros ambulatoriais e emergencia (20.000 total)
encounters={};enclist=[]
for i in range(20000):
  eid=f'A{i+1:06d}';patient=f'P{R.randint(1,N_PATIENTS):06d}';time=randt(START,END-timedelta(seconds=1))
  service=weighted(['EMERGENCIA_ADULTO','EMERGENCIA_PED','AMBULATORIO','IMAGEM','ONCOLOGIA','HEMODIALISE'],[38,12,28,12,7,3]);origin=weighted(['ESPONTANEA','REGULACAO_SUS','AGENDADO','TRANSFERENCIA_EXTERNA'],[48,20,29,3]);
  prio=weighted(['VERDE','AMARELO','LARANJA','VERMELHO'],[50,31,14,5]) if 'EMERGENCIA' in service else 'NA'
  med=R.choice(prof_by_role['MEDICO'])
  encounters[eid]=(patient,time,service)
  enclist.append((eid,patient,time,service))
  add('atendimentos',atendimento_id=eid,paciente_id=patient,entrada=dt(time),setor_entrada=service,origem=origin,modalidade=weighted(['SUS','CONVENIO','PARTICULAR'],[78,17,5]),classificacao_risco=prio,medico_responsavel_id=med,desfecho_inicial='AVALIACAO')
# internacoes: episodio por leito, incluindo ocupacoes em andamento no inicio do mes
# capacidade modelada por cama individual. Ciclos start/stop, cleaning lag, occupied by bed disjoint
admissions=[]; intervals_by_bed=collections.defaultdict(list)
for bed_id,b in beds.items():
   # estado inicial amostrado, equivale a internacao antes de inicio do mes
   current=START-timedelta(days=R.uniform(0,3.8)) if R.random()<.78 else START+timedelta(hours=R.uniform(0,30))
   while current<END:
      # categorias possuem permanencia media diferenciada
      typ=b['tipo']; mean={'UTI_ADULTO':4.6,'UTI_NEONATAL':6.2,'UTI_PEDIATRICA':4.2,'CIRURGICO':3.3,'CLINICO':3.6,'PEDIATRICO':2.7,'OBSTETRICO':1.8,'ISOLAMENTO':4.3}[typ]
      duration=max(.25,min(23,R.gammavariate(2.3,mean/2.3)))
      exit_time=current+timedelta(days=duration)
      patient=f'P{R.randint(1,N_PATIENTS):06d}'
      # select source encounter in reasonable window; add dedicated linkage encounters if none by patient
      candidates=[x for x in []] # separate internacoes may have source encounter outside 20k demand sample
      src= 'PRE_EXISTENTE' if current<START else weighted(['EMERGENCIA','ELETIVA','TRANSFERENCIA_INTERNA','REGULACAO'],[51,26,11,12])
      admission_id=f'I{len(admissions)+1:06d}'
      if src=='PRE_EXISTENTE': request=current-timedelta(hours=R.uniform(0,6))
      else: request=current-timedelta(hours=R.uniform(.5,14))
      outcome=weighted(['ALTA','OBITO','TRANSFERENCIA_EXTERNA','EVASAO','OUTRO'],[88,3,6,1,2]) if exit_time<END else 'EM_ANDAMENTO'
      med=R.choice(prof_by_role['MEDICO']);nur=R.choice(prof_by_role['ENFERMEIRO'])
      item={'internacao_id':admission_id,'paciente_id':patient,'atendimento_id':'','leito_id':bed_id,'quarto_id':b['quarto_id'],'unidade_id':b['unidade_id'],'solicitacao_leito':dt(request),'entrada_leito':dt(current),'saida_leito':dt(exit_time) if exit_time<END else '', 'tipo_saida':outcome,'origem_internacao':src,'medico_responsavel_id':med,'enfermeiro_referencia_id':nur,'prioridade':weighted(['URGENTE','ALTA','ROTINA'],[18,33,49]),'isolamento_indicado':int(typ=='ISOLAMENTO')}
      admissions.append(item);intervals_by_bed[bed_id].append((current,exit_time,admission_id))
      # post-exit bed clean, next admission after random idle time
      clean_minutes=R.randint(28,120);clean_end=exit_time+timedelta(minutes=clean_minutes)
      if exit_time<END:
       add('hotelaria_eventos',evento_id=f'H{len(rows.get("hotelaria_eventos",[]))+1:07d}',internacao_id=admission_id,quarto_id=b['quarto_id'],leito_id=bed_id,tipo_evento='SAIDA_PACIENTE',data_hora=dt(exit_time),responsavel_id='',observacao='DESOCUPACAO')
       add('higienizacoes',higienizacao_id=f'G{len(rows.get("higienizacoes",[]))+1:07d}',leito_id=bed_id,quarto_id=b['quarto_id'],internacao_anterior_id=admission_id,inicio=dt(exit_time),fim=dt(clean_end),profissional_id=R.choice(prof_by_role['HIGIENIZACAO']),status='CONCLUIDA')
       add('hotelaria_eventos',evento_id=f'H{len(rows.get("hotelaria_eventos",[]))+1:07d}',internacao_id=admission_id,quarto_id=b['quarto_id'],leito_id=bed_id,tipo_evento='LEITO_HIGIENIZADO',data_hora=dt(clean_end),responsavel_id='',observacao='PRONTO_PARA_NOVA_ALOCACAO')
      current=clean_end+timedelta(hours=R.uniform(2,28))
for item in admissions:
 add('internacoes',**item)
 add('hotelaria_eventos',evento_id=f'H{len(rows.get("hotelaria_eventos",[]))+1:07d}',internacao_id=item['internacao_id'],quarto_id=item['quarto_id'],leito_id=item['leito_id'],tipo_evento='ENTRADA_PACIENTE',data_hora=item['entrada_leito'],responsavel_id=item['enfermeiro_referencia_id'],observacao='CHECKIN')
# add transitions and procedures within windows, respecting episode and dates
for adm in admissions:
 begin=datetime.fromisoformat(adm['entrada_leito']); end=datetime.fromisoformat(adm['saida_leito']) if adm['saida_leito'] else END
 if end<=START: continue
 if R.random()<.45:
   t=max(begin,START)+timedelta(hours=R.uniform(1,10));
   if t<min(end,END):
    add('procedimentos',procedimento_id=f'PR{len(rows.get("procedimentos",[]))+1:07d}',internacao_id=adm['internacao_id'],paciente_id=adm['paciente_id'],tipo=weighted(['EXAME_IMAGEM','HEMODIALISE','ENDOSCOPIA','TERAPIA'],[42,16,18,24]),especialidade='APOIO',inicio=dt(t),fim=dt(t+timedelta(minutes=R.randint(25,110))),unidade_id=weighted(['IMAGEM','HEMODIALISE','CENTRO_CIRURGICO'],[70,18,12]),medico_id=adm['medico_responsavel_id'],situacao='REALIZADO',prioridade=adm['prioridade'])
 # create at most one elective/emergency surgery per plausible inpatient; duration bounded within stay
 if adm['unidade_id']=='CIRURGICA' and R.random()<.76 or adm['unidade_id'].startswith('UTI_ADULTO') and R.random()<.19:
   t=begin+timedelta(hours=R.uniform(1,22));endproc=t+timedelta(minutes=R.randint(45,300))
   if t>=START and endproc<min(end,END):
    procedure_id=f'C{len(rows.get("cirurgias",[]))+1:06d}'
    med=adm['medico_responsavel_id']; anest=R.choice(prof_by_role['ANESTESISTA'])
    add('cirurgias',cirurgia_id=procedure_id,internacao_id=adm['internacao_id'],paciente_id=adm['paciente_id'],especialidade=R.choice(['GERAL','CARDIACA','VASCULAR','NEUROCIRURGIA','ORTOPEDIA']),carater=weighted(['ELETIVA','URGENCIA','EMERGENCIA'],[55,34,11]),sala_id=f'SALA_SIM_{R.randint(1,12):02d}',inicio_previsto=dt(t-timedelta(minutes=R.randint(0,80))),inicio_real=dt(t),fim_real=dt(endproc),cirurgiao_id=med,anestesista_id=anest,enfermeiro_id=adm['enfermeiro_referencia_id'],status='CONCLUIDA',pos_operatorio_unidade_id=adm['unidade_id'])
    add('procedimentos',procedimento_id=f'PR{len(rows.get("procedimentos",[]))+1:07d}',internacao_id=adm['internacao_id'],paciente_id=adm['paciente_id'],tipo='CIRURGIA',especialidade='CIRURGICA',inicio=dt(t),fim=dt(endproc),unidade_id='CENTRO_CIRURGICO',medico_id=med,situacao='REALIZADO',prioridade=adm['prioridade'])
# explicit requests waiting without allocation -> backlog events, modeled independently
for k in range(110):
 t=randt(START,END-timedelta(hours=3));uid=R.choice(clinical_units)
 add('solicitacoes_pendentes',solicitacao_id=f'SP{k+1:05d}',paciente_id=f'P{R.randint(1,N_PATIENTS):06d}',entrada=dt(t),unidade_requerida=uid,prioridade=weighted(['URGENTE','ALTA','ROTINA'],[25,35,40]),status='PENDENTE_SIMULADA',motivo='SEM_ATRIBUICAO_NO_CENARIO')
# transfer between units recorded as linked chain? cross-unit transfer events from a pair of admissions same patient would require new admission representation.
# separate transfer requests as events, no unauthorized occupancy change
for k in range(230):
 adm=R.choice(admissions);beg=datetime.fromisoformat(adm['entrada_leito']);out=datetime.fromisoformat(adm['saida_leito']) if adm['saida_leito'] else END
 when=max(beg,START)+timedelta(hours=R.uniform(6,28))
 if when>=min(out,END): continue
 target=R.choice([u for u in clinical_units if u!=adm['unidade_id']])
 add('solicitacoes_transferencia',transferencia_id=f'T{k+1:05d}',internacao_id=adm['internacao_id'],paciente_id=adm['paciente_id'],unidade_origem=adm['unidade_id'],unidade_destino_solicitada=target,data_solicitacao=dt(when),status=weighted(['SOLICITADA','CANCELADA','AVALIACAO'],[60,17,23]),tipo='INTERNA_PENDENTE_NAO_EXECUTADA')
# write CSV, SQLite and comprehensive README
for table,data in rows.items():
 with open(OUT/(table+'.csv'),'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0].keys()),delimiter=';');w.writeheader();w.writerows(data)
db=OUT/'hsja_outubro_2026.sqlite'
if db.exists():db.unlink()
conn=sqlite3.connect(db)
for table,data in rows.items():
 cols=list(data[0].keys()); names=','.join('"'+c+'" '+ ('INTEGER' if all(isinstance(r[c],int) for r in data) else 'TEXT') for c in cols)
 conn.execute(f'CREATE TABLE "{table}" ({names})')
 conn.executemany(f'INSERT INTO "{table}" VALUES ({",".join("?" for c in cols)})',[[r[c] for c in cols] for r in data])
for table, col in [('leitos','quarto_id'),('leitos','unidade_id'),('quartos','unidade_id'),('atendimentos','paciente_id'),('atendimentos','entrada'),('internacoes','leito_id'),('internacoes','paciente_id'),('internacoes','entrada_leito'),('internacoes','unidade_id'),('procedimentos','internacao_id'),('cirurgias','internacao_id'),('escalas','profissional_id'),('hotelaria_eventos','leito_id'),('hotelaria_eventos','data_hora')]:
 conn.execute(f'CREATE INDEX idx_{table}_{col} ON "{table}"("{col}")')
conn.commit()
# validation
bad=0
for bid,intervals in intervals_by_bed.items():
 intervals.sort()
 for i in range(1,len(intervals)):
  if intervals[i][0]<intervals[i-1][1]:bad+=1
assert bad==0
assert len(rows['leitos'])==310 and len(rows['profissionais'])==1470 and len(rows['atendimentos'])==20000
assert all(v['paciente_id'].startswith('P') for v in rows['internacoes'])
# patient occupancy daily, average and rate
occ=[]
for d in range(31):
 when=START+timedelta(days=d,hours=12)
 num=sum(any(a<=when<b for a,b,_ in intr) for intr in intervals_by_bed.values())
 occ.append((when.date().isoformat(),num))
 with open(OUT/'ocupacao_diaria.csv','w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f,delimiter=';');w.writerow(['data','ocupados_12h','capacidade','taxa_ocupacao']);w.writerows((date,n,310,round(n/310,4)) for date,n in occ)
summary={t:len(a) for t,a in rows.items()};summary['ocupacao_media_12h']=round(sum(n for _,n in occ)/len(occ)/310,3)
summary['internacoes_iniciadas_mes']=sum(START<=datetime.fromisoformat(a['entrada_leito'])<END for a in admissions)
summary['saidas_mes']=sum(bool(a['saida_leito']) and START<=datetime.fromisoformat(a['saida_leito'])<END for a in admissions)
summary['desfechos_internacoes']=dict(collections.Counter(a['tipo_saida'] for a in admissions if a['saida_leito']))
summary['observacao']='Todos os dados sao ficcionais, sintese estatistica nao representa HSJA real.'
(OUT/'resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
README='''# Dataset totalmente SIMULADO — HSJA, outubro de 2026

**IMPORTANTE:** nao sao dados do Hospital Sao Jose do Avai. Nenhuma pessoa, quarto, profissional, escala, leito, fluxo ou atividade corresponde a registro real. O nome do hospital indica apenas o *cenario de pesquisa hipotetico*. Pessoas tem nomes explicitamente marcados como `SIM` e IDs ficticios; nenhum CPF/CRM real e utilizado.

## Parametros
- Periodo de referencia de analise: 2026-10-01 a 2026-10-31; algumas internacoes comecam antes, e outras seguem apos 31/10 (censura de periodo).
- 310 leitos por grupos de referencia (102 UTI, 93 cirurgicos, 74 clinicos, 25 pediatricos, 15 obstetricos, 1 isolamento). **A divisao em quartos e alas e totalmente inventada; nao sao plantas nem andares reais.**
- 1.470 profissionais ficticios de nove categorias. Nao e dimensionamento recomendado nem a composicao real do HSJA.
- 20.000 atendimentos ficticios, de diversas modalidades. **Atendimentos nao sao internacoes**.
- Permanencias e limpeza geradas por distribuicoes estocasticas, sem inferencia clinica; desfechos de saida sao sorteios ficticios.
- Cirurgias representam amostra vinculada a internacoes; nao equivalem a producao cirurgica real do hospital.

## Arquivos e chaves
- `pacientes.csv`: paciente_id (P...). Dados sinteticos.
- `profissionais.csv`: profissional_id (F...), categoria, especialidade, unidade_base.
- `unidades.csv`: unidade_id (servicos e unidades com leitos).
- `quartos.csv`: quarto_id, unidade_id, capacidade, ala simulada.
- `leitos.csv`: leito_id, quarto_id, unidade_id e recursos.
- `escalas.csv`: escala_id, profissional_id, unidade_id, inicio, fim. Escalas sinteticas nao validadas contra ratios clinicos.
- `atendimentos.csv`: atendimento_id, paciente_id, entrada, origem, classificacao de risco.
- `internacoes.csv`: internacao_id, paciente_id, leito_id, quarto_id, unidade_id, datas de solicitacao e ocupacao, tipo_saida (ALTA, OBITO, TRANSFERENCIA_EXTERNA, EVASAO, OUTRO, EM_ANDAMENTO), responsaveis.
- `hotelaria_eventos.csv`: entrada do paciente, saida e conclusao de limpeza; evento tem hora.
- `higienizacoes.csv`: inicio, fim, leito, profissional responsavel.
- `cirurgias.csv`: cirurgias realizadas, sala simulada, horarios e profissionais.
- `procedimentos.csv`: procedimentos vinculados a internacoes.
- `solicitacoes_transferencia.csv`: pedidos *nao executados* (evita representar mudancas de leito ficticias como ocorridas).
- `solicitacoes_pendentes.csv`: backlog sintetico independente das internacoes (nao contar como inadmissao real).
- `ocupacao_diaria.csv`: snapshots as 12h de cada dia em outubro.
- `resumo.json`: volumetria e taxas calculadas.
- `hsja_outubro_2026.sqlite`: tabelas SQLite com indices para exploracao inicial.

CSV usa separador `;`, UTF-8 BOM, horario local sem offset (`YYYY-MM-DD HH:MM:SS`). Todos os IDs sao artificiais.

## Restricoes e limites do dataset
- Uma cama nunca possui duas ocupacoes sobrepostas; leitos sao liberados somente apos uma higienizacao.
- Operacao gerada por ciclo independente de cada leito, nao por simulacao integral das filas do hospital. Portanto, solicitação/espera nao representa sistema validado de regulacao.
- Os horarios das escalas nao foram usados para validar compatibilidade do medico/enfermeiro responsavel pela internacao. Ajustar antes de testar otimizacao clinica.
- Cirurgias e procedimentos podem nao ter equipe integral documentada. Para pesquisa operacional, completar recursos materiais e certificacoes quando necessario.
- A simulacao nao captura readmissoes, riscos associados a doencas, idade apropriada a unidade ou transferencias executadas entre leitos. **Nao usar para treinar modelo clinico real ou tomar decisoes sobre pacientes.**
- `saidas` sao as saidas de leito dentro de outubro, nao necessariamente altas institucionais de um individuo.

## Consultas SQL para teste
```sql
SELECT tipo_saida, count(*) FROM internacoes WHERE saida_leito <> '' GROUP BY tipo_saida;
SELECT unidade_id, count(*) FROM leitos GROUP BY unidade_id;
SELECT date(entrada_leito), count(*) FROM internacoes WHERE entrada_leito >= '2026-10-01' GROUP BY 1 ORDER BY 1;
SELECT l.unidade_id, count(*) FROM internacoes i JOIN leitos l USING(leito_id) WHERE i.entrada_leito < '2026-10-15 12:00:00' AND (i.saida_leito='' OR i.saida_leito>'2026-10-15 12:00:00') GROUP BY 1;
```

## Uso em grafo
Vertices: Paciente, Profissional, Unidade, Quarto, Leito, Internacao, Atendimento, Procedimento, Cirurgia, Escala e Higienizacao.
Arestas derivadas de FKs: PACIENTE_TEM_ATENDIMENTO, PACIENTE_TEM_INTERNACAO, INTERNACAO_OCUPA_LEITO, LEITO_EM_QUARTO, QUARTO_EM_UNIDADE, MEDICO_RESPONSAVEL, ENFERMEIRO_REFERENCIA, INTERNACAO_TEM_CIRURGIA, CIRURGIA_COM_MEDICO, PROFISSIONAL_TEM_ESCALA e LEITO_PASSOU_HIGIENIZACAO.
Datas de validade: inicio/saida da internacao; inicio/fim da escala; datas do procedimento e da higienizacao.

## Reproducao
`python gerar_hsja_simulado.py` (stdlib; semente 20261008; diretorio /mnt/data/hsja_simulado). Nao e necessidade de acesso ao HSJA.
'''
(OUT/'LEIA_ME.md').write_text(README,encoding='utf-8')
conn.close()
archive=Path('/mnt/data/HSJA_dataset_simulado_outubro_2026.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for path in OUT.iterdir():z.write(path,arcname=path.name)
 z.write('/mnt/data/gerar_hsja_simulado.py',arcname='gerar_hsja_simulado.py')
print(json.dumps(summary,ensure_ascii=False,indent=2));print('ZIP',archive,'bytes',archive.stat().st_size)
