"""Fixture autoral determinística; não reproduz pacientes nem dados do artigo."""
from datetime import datetime, timedelta, timezone
import random

VERSION = 'hospital-longitudinal-fixture-v1'
ARTICLE = {'title': 'Synthetic Hospital: An Open, Verifiable, Physician-Validated Longitudinal EHR Benchmark',
           'authors': ['Christine Park', 'Valerie Chen', 'Tim Dettmers'],
           'reference': 'arXiv:2609.30027v1', 'url': 'https://arxiv.org/abs/2609.30027',
           'relationship': 'Inspiração metodológica; dados e validação do artigo não foram importados.'}


def iso(value):
    return value.isoformat(timespec='seconds').replace('+00:00', 'Z')


def timestamp(value):
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()*1000)


def build(seed=42):
    rng = random.Random(seed)
    nodes, edges, documents, patients, tasks = [], [], [], [], []

    def node(key, label, **properties):
        nodes.append({'key': key, 'label': label, 'properties': properties})

    def edge(a, b, kind):
        edges.append({'from_key': a, 'to_key': b, 'type': kind})

    node('U001', 'Unidade', nome='UNIDADE_SIM', synthetic=True)
    for room in range(1, 6):
        key = f'Q{room:03}'
        node(key, 'Quarto', capacidade=4, synthetic=True)
        edge(key, 'U001', 'EM_UNIDADE')
    for number in range(1, 21):
        patient = f'P{number:03}'
        bed = f'L{number:03}'
        room = f'Q{(number-1)//4+1:03}'
        split = 'train' if number <= 12 else 'validation' if number <= 16 else 'test'
        patients.append({'id': patient, 'split': split, 'name': f'PACIENTE_SIM_{number:03}'})
        node(patient, 'Paciente', nome=patients[-1]['name'], synthetic=True)
        node(bed, 'Leito', recurso='RECURSO_A' if number % 2 else 'RECURSO_B', synthetic=True)
        edge(bed, room, 'EM_QUARTO')
        required = 'RECURSO_A' if number % 2 else 'RECURSO_B'
        for encounter in range(1, 4):
            identifier = f'{patient}-A{encounter:02}'
            at = datetime(2026, 1, 1, 8, tzinfo=timezone.utc) + timedelta(days=(number-1)*2+(encounter-1)*30)
            exit_at = at + timedelta(hours=4)
            release = exit_at + timedelta(minutes=rng.choice([45, 60, 90]))
            source = 'SRC-' + identifier
            admission = 'INT-' + identifier
            resource_fact = 'OBS-' + identifier + '-R'
            cleaning_fact = 'OBS-' + identifier + '-L'
            node(identifier, 'Atendimento', inicio=iso(at), fim=iso(exit_at), synthetic=True)
            node(admission, 'Internacao', entrada=iso(at), saida=iso(exit_at), liberacao=iso(release), synthetic=True)
            node(source, 'Fonte', generator=VERSION, seed=seed, version='v1', validation_status='synthetic_rule_checked')
            node(resource_fact, 'Observacao', tipo='requisito_operacional', valor=required, instante=iso(at), synthetic=True)
            node(cleaning_fact, 'Observacao', tipo='fim_higienizacao', valor=iso(release), instante=iso(release), synthetic=True)
            for a, b, kind in [(patient, identifier, 'TEM_ATENDIMENTO'), (identifier, admission, 'TEM_INTERNACAO'),
                               (admission, bed, 'OCUPA'), (identifier, resource_fact, 'TEM_OBSERVACAO'),
                               (identifier, cleaning_fact, 'TEM_OBSERVACAO'), (resource_fact, source, 'DERIVADA_DE'),
                               (cleaning_fact, source, 'DERIVADA_DE')]:
                edge(a, b, kind)
            text = (f'{patient} atendimento {identifier}. Entrada={iso(at)}; saída={iso(exit_at)}. '
                    f'{resource_fact}: requisito operacional explícito={required}. '
                    f'{cleaning_fact}: leito {bed} indisponível até fim da higienização={iso(release)}. '
                    'Cenário fictício; nenhuma indicação clínica inferida.')
            documents.append({'key': 'DOC-' + identifier, 'patient': patient, 'encounter': identifier,
                'source_id': source, 'source_version': 'v1', 'text': text, 'valid_from': int(at.timestamp()*1000),
                'embedding': [float(encounter == j) for j in range(1, 4)], 'facts': [resource_fact, cleaning_fact],
                'release_at': iso(release), 'entry_at': iso(at), 'exit_at': iso(exit_at), 'bed': bed,
                'resource': required, 'split': split})
        patient_docs = [d for d in documents if d['patient'] == patient]
        tasks.append({'id': 'T-' + patient, 'patient': patient, 'split': split,
            'question': f'Quais atendimentos e registros operacionais existem para {patient}?',
            'expected_sources': [d['source_id'] for d in patient_docs],
            'expected_facts': [fact for d in patient_docs for fact in d['facts']]})
    fixture = {'generator_version': VERSION, 'seed': seed, 'article': ARTICLE,
               'patients': patients, 'nodes': nodes, 'edges': edges, 'documents': documents}
    gold = {'visibility': 'evaluator_only_not_uploaded', 'tasks': tasks,
            'correction_task': {'patient': 'P001', 'document_key': 'DOC-P001-A03',
                                'expected_old_version': 'v1', 'expected_new_version': 'v2'}}
    validate(fixture)
    return fixture, gold


def validate(fixture):
    ids = [node['key'] for node in fixture['nodes']]
    if len(ids) != len(set(ids)):
        raise ValueError('IDs estruturais duplicados')
    known = set(ids)
    for edge in fixture['edges']:
        if edge['from_key'] not in known or edge['to_key'] not in known:
            raise ValueError('Relação sem endpoint')
    sources, by_patient, by_bed = set(), {}, {}
    for doc in fixture['documents']:
        if doc['source_id'] in sources:
            raise ValueError('Fonte reutilizada entre encontros')
        sources.add(doc['source_id'])
        begin, end, release = map(timestamp, [doc['entry_at'], doc['exit_at'], doc['release_at']])
        if not begin < end <= release:
            raise ValueError('Ordem temporal inválida')
        by_patient.setdefault(doc['patient'], []).append((begin, release))
        by_bed.setdefault(doc['bed'], []).append((begin, release))
    for intervals in [*by_patient.values(), *by_bed.values()]:
        ordered = sorted(intervals)
        if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Ocupações sobrepostas ou leito reutilizado antes da limpeza')
    if len(fixture['patients']) != 20 or any(len(by_patient.get(p['id'], [])) != 3 for p in fixture['patients']):
        raise ValueError('Fixture deve ter 20 pacientes e três atendimentos por paciente')
