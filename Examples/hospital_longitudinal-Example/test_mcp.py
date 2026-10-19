import unittest
from dataset import build
from demo_mcp import patient_slice, evidence_rows


class HospitalMcpTests(unittest.TestCase):
    def test_slice_has_no_other_patient_or_dangling_edge(self):
        nodes, edges = patient_slice(build()[0])
        keys = {n['key'] for n in nodes}
        self.assertEqual([n['key'] for n in nodes if n['label'] == 'Paciente'], ['P001'])
        self.assertTrue(all(e['from_key'] in keys and e['to_key'] in keys for e in edges))
        self.assertEqual(sum(n['label'] == 'Documento' for n in nodes), 3)
        self.assertFalse(any('P002' in str(n) for n in nodes))

    def test_truncation_and_wrong_patient_fail_closed(self):
        with self.assertRaises(ValueError):
            evidence_rows({'truncated': True, 'resultados': []})
        with self.assertRaises(ValueError):
            evidence_rows({'truncated': False, 'resultados': [{'node': {
                'label': 'Documento', 'properties': {'patient': 'P002'}}}]})


if __name__ == '__main__':
    unittest.main()
