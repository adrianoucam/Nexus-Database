"""Validação exata contra fatos estruturados recuperados pelo MCP, sem gabarito."""
import json


def response_schema(record_count):
    fields = {name: {'type': 'string'} for name in
              ('atendimento', 'entrada', 'saida', 'liberacao', 'recurso', 'fonte', 'versao')}
    fields['observacoes'] = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 2}
    return {'type': 'object', 'additionalProperties': False, 'required': ['atendimentos'],
        'properties': {'atendimentos': {'type': 'array', 'minItems': record_count, 'maxItems': record_count,
            'items': {'type': 'object', 'additionalProperties': False,
                      'properties': fields, 'required': list(fields)}}}}


def expected_records(result):
    if result.get('truncated'):
        raise ValueError('Evidência truncada')
    nodes = {}
    for row in result['resultados']:
        node = row['node']
        key = node['properties']['external_id']
        if key in nodes:
            raise ValueError('Identificador duplicado na evidência')
        nodes[key] = node
    records = []
    for node in nodes.values():
        if node['label'] != 'Documento':
            continue
        doc = node['properties']
        encounter = doc['external_id'].removeprefix('DOC-')
        admission = nodes['INT-' + encounter]['properties']
        resource_id, cleaning_id = 'OBS-' + encounter + '-R', 'OBS-' + encounter + '-L'
        resource = nodes[resource_id]['properties']
        cleaning = nodes[cleaning_id]['properties']
        source = nodes[doc['source_id']]['properties']
        if (doc['patient'] != 'P001' or not encounter.startswith('P001-A')
                or source['version'] != doc['version']
                or admission['liberacao'] != cleaning['valor']
                or cleaning['instante'] != cleaning['valor']):
            raise ValueError('Evidência inconsistente')
        records.append({'atendimento': encounter, 'entrada': admission['entrada'],
            'saida': admission['saida'], 'liberacao': cleaning['valor'],
            'recurso': resource['valor'], 'fonte': doc['source_id'], 'versao': doc['version'],
            'observacoes': [resource_id, cleaning_id]})
    if not records:
        raise ValueError('Nenhum atendimento com evidência')
    return sorted(records, key=lambda r: r['atendimento'])


def validate_response(answer, expected, finish_reason=None):
    """Não recupera JSON de prosa, não corrige nem completa saída divergente."""
    def reject(code):
        return {'accepted': False, 'reason': code, 'records': []}

    if finish_reason == 'length':
        return reject('OUTPUT_TRUNCATED')

    def unique_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('duplicate key')
            obj[key] = value
        return obj

    try:
        payload = json.loads(answer, object_pairs_hook=unique_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError):
        return reject('INVALID_JSON')
    if type(payload) is not dict or set(payload) != {'atendimentos'} or type(payload['atendimentos']) is not list:
        return reject('INVALID_SCHEMA')
    records = payload['atendimentos']
    if len(records) != len(expected):
        return reject('INCOMPLETE_OR_EXTRA_RECORDS')
    known = {r['atendimento']: r for r in expected}
    seen = set()
    for row in records:
        if type(row) is not dict or set(row) != set(expected[0]):
            return reject('INVALID_RECORD_SCHEMA')
        if any(type(row[k]) is not str for k in row if k != 'observacoes'):
            return reject('INVALID_FIELD_TYPE')
        facts = row['observacoes']
        if type(facts) is not list or any(type(f) is not str for f in facts):
            return reject('INVALID_FACT_IDS')
        encounter = row['atendimento']
        if encounter in seen or encounter not in known:
            return reject('DUPLICATE_OR_UNKNOWN_ENCOUNTER')
        seen.add(encounter)
        for key, value in known[encounter].items():
            if key == 'observacoes':
                if len(facts) != len(value) or set(facts) != set(value):
                    return reject('FACT_IDS_MISMATCH')
            elif row[key] != value:
                return reject('EVIDENCE_MISMATCH_' + key.upper())
    return {'accepted': True, 'reason': 'EXACT_MATCH_TO_MCP_EVIDENCE',
            'records': sorted(records, key=lambda r: r['atendimento'])}


def display_response(validation):
    if not validation['accepted']:
        return 'Resposta recusada: ' + validation['reason'] + '. Nenhum conteúdo da LLM foi apresentado.'
    return 'Resposta validada contra a evidência MCP:\n' + '\n'.join(
        f"{r['atendimento']}: entrada {r['entrada']}; saída {r['saida']}; liberação {r['liberacao']}; "
        f"recurso {r['recurso']}; [{r['fonte']}@{r['versao']}]; " + ', '.join(r['observacoes'])
        for r in validation['records'])
