import unittest
from datetime import datetime
from optimization import snapshot, solve, audit, min_cost, matching


def request(i, priority='ROTINA', **extra):
    return dict(solicitacao_id=str(i), paciente_id=str(i), entrada='2026-10-01 00:00:00',
                unidade_requerida='U', prioridade=priority, status='PENDENTE_SIMULADA', **extra)


def bed(i, ventilator='0'):
    return dict(leito_id=str(i), quarto_id=str(i), unidade_id='U', ativo='1',
                suporte_isolamento='0', ventilador=ventilator)


class Tests(unittest.TestCase):
    def test_augment_and_cost(self):
        rows = [request(1), request(2, ventilador_requerido='1')]
        beds = [bed(1, '1'), bed(2)]
        self.assertEqual(len(matching(rows, beds)), 2)
        self.assertEqual(len(min_cost(rows, beds, datetime(2026, 10, 15))), 2)
        rows.append(request(3, 'URGENTE'))
        self.assertIn(2, min_cost(rows, beds, datetime(2026, 10, 15)))

    def test_methods_and_determinism(self):
        rows, beds, at = [request(1), request(2, 'URGENTE')], [bed(1)], datetime(2026, 10, 15)
        for method in ('convencional', 'matching', 'fluxo_custo_minimo', 'genetico', 'robusto'):
            result = solve(method, rows, beds, at, {})
            audit(result, rows, beds)
            self.assertEqual(result, solve(method, rows, beds, at, {}))
        self.assertEqual(solve('genetico', [], [], at, {}), {})

    def test_temporal_cleaning_and_future(self):
        data = {'leitos': [bed(1)], 'internacoes': [dict(internacao_id='I', paciente_id='P',
            leito_id='1', unidade_id='U', entrada_leito='2026-09-30 00:00:00',
            saida_leito='2026-10-01 10:00:00')],
            'higienizacoes': [dict(internacao_anterior_id='I', leito_id='1',
                inicio='2026-10-01 10:00:00', fim='2026-10-01 12:00:00')],
            'solicitacoes_pendentes': [request(1)]}
        self.assertEqual(snapshot(data, datetime(2026, 10, 1, 11))[1], [])
        self.assertEqual(len(snapshot(data, datetime(2026, 10, 1, 12))[1]), 1)
        self.assertEqual(snapshot(data, datetime(2026, 10, 1, 12), ['1'])[1], [])
        data['internacoes'][0]['saida_leito'] = ''
        self.assertEqual(snapshot(data, datetime(2026, 10, 31))[1], [])


if __name__ == '__main__':
    unittest.main()
