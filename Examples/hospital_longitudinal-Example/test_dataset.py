"""Testes de fixture, integridade e avaliação; sem servidor nem modelo."""
import copy
import unittest
from dataset import build, validate
from evaluation import metrics, answer_from_rows, evaluate_generated


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.fixture, self.gold = build(42)

    def test_reproducible_and_seed_changes_cleaning(self):
        self.assertEqual((self.fixture, self.gold), build(42))
        self.assertNotEqual(self.fixture['documents'], build(43)[0]['documents'])

    def test_exact_size_and_disjoint_sources(self):
        self.assertEqual(len(self.fixture['patients']), 20)
        self.assertEqual(len(self.fixture['documents']), 60)
        self.assertEqual(len({d['source_id'] for d in self.fixture['documents']}), 60)
        self.assertEqual([sum(p['split'] == s for p in self.fixture['patients']) for s in ['train', 'validation', 'test']], [12, 4, 4])

    def test_dangling_relationship_is_rejected(self):
        self.fixture['edges'][0]['from_key'] = 'MISSING'
        with self.assertRaisesRegex(ValueError, 'endpoint'):
            validate(self.fixture)

    def test_invalid_cleaning_timeline_is_rejected(self):
        doc = self.fixture['documents'][0]
        doc['release_at'] = doc['entry_at']
        with self.assertRaisesRegex(ValueError, 'temporal'):
            validate(self.fixture)

    def test_overlapping_patient_encounters_are_rejected(self):
        self.fixture['documents'][1].update({key: self.fixture['documents'][0][key]
                                           for key in ['entry_at', 'exit_at', 'release_at']})
        with self.assertRaisesRegex(ValueError, 'sobrepostas'):
            validate(self.fixture)

    def test_perfect_retrieval_and_wrong_evidence(self):
        task = self.gold['tasks'][0]
        rows = [{'origin': {'id': d['source_id']}, 'excerpt': d['text']} for d in self.fixture['documents'][:3]]
        good = metrics(rows, task['expected_sources'], task['expected_facts'])
        self.assertEqual(good['recall_at_k'], 1.)
        self.assertEqual(good['ndcg_at_k'], 1.)
        wrong = self.fixture['documents'][3]
        rows[0] = {'origin': {'id': wrong['source_id']}, 'excerpt': wrong['text']}
        bad = metrics(rows, task['expected_sources'], task['expected_facts'])
        self.assertLess(bad['precision_at_k'], 1.)
        self.assertTrue(bad['unknown_fact_ids'])

    def test_no_evidence_requires_abstention(self):
        result = answer_from_rows([])
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['citations'], [])

    def test_generated_answer_flags_stale_and_unknown_citations(self):
        evidence = [{'origin': {'id': 'SRC-P001-A01', 'version': 'v2'}}]
        result = evaluate_generated('SRC-P001-A01@v1 OBS-P002-A01-R', evidence, ['OBS-P001-A01-R'])
        self.assertEqual(result['unknown_or_stale_citations'], ['SRC-P001-A01@v1'])
        self.assertEqual(result['omitted_fact_ids'], ['OBS-P001-A01-R'])
        self.assertEqual(result['unknown_fact_ids'], ['OBS-P002-A01-R'])

    def test_ground_truth_has_no_node_for_upload(self):
        self.assertEqual(self.gold['visibility'], 'evaluator_only_not_uploaded')
        self.assertNotIn('tasks', self.fixture)
        self.assertTrue(all(n['label'] not in {'Task', 'GroundTruth'} for n in self.fixture['nodes']))


if __name__ == '__main__':
    unittest.main()
