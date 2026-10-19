import unittest
from pathlib import Path
from app import Hospital


class HospitalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = Hospital(Path(__file__).with_name('HSJA_dataset_simulado_outubro_2026.zip'))

    def test_view_partition_and_block(self):
        view = self.h.view(15, 12, 'convencional')
        self.assertEqual(len(view['beds']), 310)
        proposed = [b for b in view['beds'] if b['state'] == 'proposta']
        self.assertEqual(len(proposed), view['metrics']['allocated'])
        blocked = self.h.view(15, 12, 'convencional', [proposed[0]['leito_id']])
        self.assertFalse(any(b['proposal'] for b in blocked['beds']
                             if b['leito_id'] == proposed[0]['leito_id']))

    def test_month_all_methods(self):
        for method in ('convencional', 'matching', 'fluxo_custo_minimo', 'genetico', 'robusto'):
            month = self.h.month(12, method)
            self.assertEqual(len(month), 31)
            self.assertTrue(all(r['hard_violations'] == 0 for r in month))

    def test_invalid_inputs(self):
        for args in [(0,12,'matching'), (15,24,'matching'), (15,12,'cuda'), (15,12,'matching',['invalid'])]:
            with self.assertRaises(ValueError):
                self.h.view(*args)


if __name__ == '__main__':
    unittest.main()
