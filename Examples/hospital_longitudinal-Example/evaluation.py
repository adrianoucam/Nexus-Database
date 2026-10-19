"""Avaliação de IDs estruturados; não é um avaliador clínico de texto livre."""
import math
import re


def metrics(rows, expected_sources, expected_facts, k=3):
    selected = rows[:k]
    sources = [row['origin']['id'] for row in selected]
    expected = set(expected_sources)
    relevant = [int(source in expected) for source in sources]
    retrieved_facts = set(re.findall(r'OBS-P\d{3}-A\d{2}-[RL]', ' '.join(row['excerpt'] for row in selected)))
    hits = len(set(sources) & expected)
    dcg = sum(rel/math.log2(i+2) for i, rel in enumerate(relevant))
    ideal = sum(1/math.log2(i+2) for i in range(min(k, len(expected))))
    return {'precision_at_k': sum(relevant)/k, 'recall_at_k': hits/len(expected) if expected else 0.,
            'ndcg_at_k': dcg/ideal if ideal else 0., 'k': k, 'returned': len(selected),
            'fact_id_coverage': len(retrieved_facts & set(expected_facts))/len(set(expected_facts)) if expected_facts else 0.,
            'unknown_fact_ids': sorted(retrieved_facts - set(expected_facts))}


def answer_from_rows(rows):
    if not rows:
        return {'status': 'insufficient_evidence', 'answer': 'Evidência autorizada insuficiente.', 'citations': []}
    return {'status': 'evidence_available', 'answer': '\n'.join(
        f"[{r['origin']['id']}@{r['origin']['version']}] {r['excerpt']}" for r in rows),
        'citations': [{'node_id': r['node_id'], 'source_id': r['origin']['id'], 'version': r['origin']['version']} for r in rows]}


def evaluate_generated(text, evidence, expected_facts):
    valid = {f"{row['origin']['id']}@{row['origin']['version']}" for row in evidence}
    citations = set(re.findall(r'SRC-P\d{3}-A\d{2}@v\d+', text))
    mentioned = set(re.findall(r'OBS-P\d{3}-A\d{2}-[RL]', text))
    expected = set(expected_facts)
    return {'scope': 'identifier_and_citation_checks_only_not_clinical_validation',
        'valid_citations': sorted(citations & valid), 'unknown_or_stale_citations': sorted(citations-valid),
        'source_citation_coverage': len(citations & valid)/len(valid) if valid else 0.,
        'fact_id_coverage': len(mentioned & expected)/len(expected) if expected else 0.,
        'omitted_fact_ids': sorted(expected-mentioned), 'unknown_fact_ids': sorted(mentioned-expected),
        'review_required': True}
