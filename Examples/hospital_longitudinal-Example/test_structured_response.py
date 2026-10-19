import copy
import json
import unittest
from dataset import build
from demo_mcp import patient_slice
from structured_response import expected_records, validate_response, display_response


class StructuredTests(unittest.TestCase):
    def setUp(self):
        nodes, _ = patient_slice(build()[0])
        self.result = {'truncated': False, 'resultados': [
            {'node': n | {'id': i}} for i, n in enumerate(nodes)]}
        self.expected = expected_records(self.result)

    def validate(self, rows):
        return validate_response(json.dumps({'atendimentos': rows}), self.expected)

    def test_accepts_exact_records_in_any_order(self):
        result = self.validate(self.expected[::-1])
        self.assertTrue(result['accepted'])
        self.assertIn('13:30:00Z', display_response(result))

    def test_each_changed_field_is_rejected(self):
        for field in self.expected[0]:
            with self.subTest(field=field):
                rows = copy.deepcopy(self.expected)
                rows[0][field] = ['OBS-INVENTADA'] if field == 'observacoes' else 'DIVERGENTE'
                self.assertFalse(self.validate(rows)['accepted'])

    def test_previous_gemma_errors_and_swapped_encounters(self):
        rows = copy.deepcopy(self.expected)
        rows[0]['liberacao'] = rows[0]['saida']
        self.assertFalse(self.validate(rows)['accepted'])
        rows = copy.deepcopy(self.expected)
        rows[1]['entrada'] = rows[2]['entrada']
        self.assertFalse(self.validate(rows)['accepted'])

    def test_missing_extra_duplicate_and_extra_prose_fields(self):
        for rows in [self.expected[:2], self.expected + self.expected[:1],
                     [self.expected[0]] * 3,
                     [self.expected[0] | {'recomendacao': 'INSEGURO'}, *self.expected[1:]]]:
            self.assertFalse(self.validate(rows)['accepted'])

    def test_malformed_duplicate_keys_and_truncation(self):
        for text in ['```json\n{}\n```', '{', '{"atendimentos":[],"atendimentos":[]}',
                     'texto livre', '{"atendimentos":NaN}']:
            self.assertFalse(validate_response(text, self.expected)['accepted'])
        text = json.dumps({'atendimentos': self.expected})
        self.assertFalse(validate_response(text, self.expected, 'length')['accepted'])

    def test_rejection_does_not_display_candidate(self):
        result = validate_response('CONTEUDO_DIVERGENTE_SECRETO', self.expected)
        self.assertNotIn('CONTEUDO_DIVERGENTE_SECRETO', display_response(result))
        self.assertEqual(result['records'], [])

    def test_conflicting_database_facts_fail_closed(self):
        for row in self.result['resultados']:
            if row['node']['key'] == 'INT-P001-A01':
                row['node']['properties']['liberacao'] = 'ERRADO'
        with self.assertRaises(ValueError):
            expected_records(self.result)


if __name__ == '__main__':
    unittest.main()
