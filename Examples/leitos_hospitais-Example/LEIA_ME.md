# Dataset totalmente SIMULADO — HSJA, outubro de 2026

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

- `arestas_grafo.csv`: arestas orientadas para importar no NexusDB. Também disponíveis na tabela SQLite `arestas_grafo`.
