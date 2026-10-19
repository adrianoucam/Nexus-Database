# Como aproveitar Synthetic Hospital no exemplo NexusDB

Análise de 19/10/2026. Referência: Christine Park, Valerie Chen e Tim Dettmers, *Synthetic Hospital: An Open, Verifiable, Physician-Validated Longitudinal EHR Benchmark*, preprint arXiv:2609.30027v1 fornecido pelo usuário. A leitura incluiu a metodologia, avaliações, limitações e apêndices de geração/rotulagem, além da inspeção visual do pipeline da página 2.

Esta é uma proposta de evolução, não uma implementação nem uma validação clínica. O PDF original não foi modificado. Nenhum dado real ou dataset externo foi importado.

Atualização de 19/10/2026: o primeiro piloto está implementado separadamente em [hospital_longitudinal-Example](../hospital_longitudinal-Example/README.md), com fixture autoral e testes reais no NexusDB. As propostas mais amplas abaixo, como validação clínica e FHIR, continuam fora do escopo entregue.

## 1. Conclusão

O artigo é uma boa referência para acrescentar um benchmark longitudinal de recuperação e explicação ao hospital. Ele não fornece calibração suficiente para substituir os parâmetros de ocupação, chegadas, duração de internação ou escala de profissionais do simulador atual.

O trabalho separa três coisas que o exemplo também deveria separar: fatos estruturados do paciente, documentação visível ao agente e respostas de referência usadas pelo avaliador. O texto produzido por uma LLM não deve criar a verdade de referência com a qual essa própria LLM será avaliada.

## 2. Diferença de finalidade

| Componente existente | Finalidade | Contribuição possível do artigo |
|---|---|---|
| `gerar_hsja_simulado.py` | Gerar dados operacionais sintéticos | Melhorar continuidade por paciente, proveniência e validações |
| `optimization.py` e painel | Comparar alocações em snapshots independentes | Receber requisitos explícitos e auditáveis, sem inferência clínica automática |
| `temporal_hospital_demo.rs` e `temporal_graph_demo.py` | Exercitar histórico, projeções e caminhos | Acrescentar observações/documentos com versões e perguntas temporais |
| GraphRAG/MCP/LLM | Recuperar e explicar evidências | Medir omissões, citações, autorização e abstenção contra um gabarito separado |

O artigo apresenta 1.268 pacientes e 5.602 encontros construídos a partir de fontes educacionais. Isso não significa uma população hospitalar representativa. Seu próprio apêndice H distingue o benchmark de uma simulação populacional calibrada.

## 3. Mudanças prioritárias

### A. Paciente longitudinal coerente

Gerar primeiro uma identidade sintética estável e uma sequência de episódios. Vincular internações, procedimentos, exames, solicitações e documentos à mesma identidade e ao atendimento correspondente.

No gerador atual, vários eventos e pedidos são sorteados e a ocupação é construída por ciclos de leito; isso é útil para um cenário operacional, mas não garante, por si só, uma trajetória clínica individual coerente. Não basta acrescentar notas narrativas a esses sorteios.

A metodologia do artigo restringe o agrupamento por compatibilidade demográfica e ligações clínicas. Para o nosso primeiro piloto, é melhor usar fixtures autorais pequenas e regras explícitas, sem declarar que reproduzem o algoritmo ou a validação médica do artigo.

### B. Proveniência em cada fato

Acrescentar campos como `source_id`, `source_version`, `generator_version`, `seed`, `validation_status` e identificador da regra geradora. Quando houver um documento educacional real, conservar a referência à fonte e ao trecho; em uma fixture inventada, registrar claramente que a fonte é uma regra sintética.

Guardar `code_system`, `code_version` e `code` quando códigos terminológicos forem utilizados. Uma sugestão de código por LLM deve permanecer candidata até ser conferida contra a terminologia apropriada. Não declarar suporte a ICD-10-CM, SNOMED CT ou LOINC apenas por criar campos com esses nomes.

### C. Fatos antes de narrativas

Pipeline proposto:

```text
Fixture/regra documentada
  → fatos e relações determinísticos
  → timeline validada
  → gabarito separado
  → documentos visíveis ao usuário/agente
  → recuperação NexusDB
  → explicação opcional por LLM
  → avaliação
```

Se uma LLM renderizar a narrativa, validar que os IDs, datas e fatos obrigatórios não foram alterados. O texto não deve sobrescrever o grafo nem o gabarito. A criação do benchmark do artigo também usa LLM em etapas intermediárias e possui uma exceção de referência textual para indicação de imagem; não se deve descrevê-lo como inteiramente livre de geração por modelo.

### D. Avaliação independente

Para recuperação, medir presença das evidências relevantes com Precision@k, Recall@k e, havendo relevância graduada, nDCG@k. Definir previamente quais fontes são necessárias para responder cada pergunta.

Para respostas, avaliar fatos corretos, fatos omitidos, afirmações sem suporte e citações válidas. Não usar apenas “a LLM retornou texto” como critério de qualidade. Um avaliador por IDs e campos estruturados pode ser determinístico; interpretação clínica de narrativas exige revisão especializada e não é garantida por comparação de strings.

Separar pacientes e fontes entre os conjuntos de desenvolvimento e teste. Documentos do mesmo paciente não devem aparecer em ambos os lados, e o arquivo de respostas de referência não pode ser publicado ao modelo, à chave de API ou ao catálogo MCP.

### E. Tempo, autorização e abstenção

Conservar o tempo de validade do fato e o tempo em que o sistema tomou conhecimento dele. As perguntas devem distinguir “o que sabemos hoje sobre ontem?” de “o que era conhecido ontem?”. Usar watermark real do NexusDB, não um horário inventado pelo gerador.

Testar resultados sem evidência, documentos retirados, contexto parcial, permissão revogada e acesso a outro paciente. As ferramentas MCP brutas atuais autorizam leitura por banco; não oferecem automaticamente segregação clínica por paciente. Para um piloto multiusuário, usar bancos separados ou procedimentos knowledge com escopo apropriado, em vez de filtrar informações confidenciais apenas no prompt.

## 4. Modelo de grafo proposto

```text
Paciente → Atendimento → Observacao
                    ├→ Procedimento
                    └→ Documento
Observacao → Fonte
Documento → Fonte
Internacao → Leito → Quarto → Unidade
Atendimento → Internacao
```

As observações precisam distinguir uma afirmação documentada, uma negação explícita, um fato desconhecido e uma hipótese. Proximidade vetorial não deve criar uma relação causal ou uma indicação clínica.

O artigo serve também como referência para interoperabilidade, mas o NexusDB atual não se torna um servidor FHIR R4 ao adotar esse modelo. Um adaptador FHIR exigiria contratos, versionamento, validação e testes próprios.

## 5. Primeiro marco recomendado

Criar um laboratório separado, por exemplo `hospital_longitudinal-Example`, preservando o painel de alocação atual. Escopo inicial proposto: 20 pacientes fictícios, três atendimentos por paciente, observações/documentos de fixture, relações de proveniência e correções temporais controladas. Esses números são uma escolha de engenharia para o piloto, não um resultado do artigo.

Perguntas de teste que não exigem inferência clínica autônoma:

1. Quais atendimentos pertencem a este paciente e em que ordem ocorreram?
2. Quais registros sustentam a indisponibilidade de um leito no instante consultado?
3. Qual era a última informação registrada antes de uma correção?
4. Qual documento fundamenta a exigência de recurso explicitamente cadastrada no cenário?
5. Há evidência autorizada suficiente para responder, ou o sistema deve se abster?

Critérios de aceite: referências válidas; ausência de sobreposição indevida; datas e IDs consistentes; gabarito invisível ao agente; leituras temporais verificadas; nenhuma evidência de outro escopo; relatório de recuperação e de omissões; geração LLM marcada como revisável. Requisitos clínicos não devem ser deduzidos automaticamente a partir de diagnósticos gerados.

## 6. O que não concluir do artigo

- A avaliação de realismo relatada pelos autores usou dez médicos e dez prontuários, com cem julgamentos. Isso não valida o nosso simulador nem demonstra representatividade de uma população.
- O artigo declara limitações para erros documentais, contradições e dados ausentes. Introduzir esses cenários seria uma extensão nossa, com gabarito controlado, não uma funcionalidade já resolvida pela referência.
- Mais interação agentic não garantiu melhores resultados nas condições avaliadas. Compare contexto direto, recuperação determinística e agente com ferramentas na mesma tarefa; não acrescente um loop MCP apenas por parecer mais sofisticado.
- Os resultados do artigo não podem ser transferidos aos modelos GGUF locais, ao nosso dataset ou ao NexusDB sem novas medições.
- O artigo não fornece taxa de chegada, permanência, pessoal ou dimensionamento apropriado para um hospital real. Essas distribuições operacionais precisam de fontes e validação independentes.

## 7. Evidências e referências de leitura

No PDF fornecido: seção 3 e figura 1 (fatos, geração e proveniência); seção 3.1 (splits por paciente); tabela 2 (tarefas/métricas); seção 4.1 (escopo do estudo de realismo); seção 5.3 (comparação agentic); seção 6 (limitações); apêndices E e F (trajetórias e gabaritos); apêndice H (diferença entre benchmark e população).

No checkout: [limites do simulador de leitos](README_OTIMIZACAO.md), [gerador atual](gerar_hsja_simulado.py), [histórico temporal](../../Docs/TEMPORAL_ENGINE.md), [conhecimento e escopo](../../Docs/KNOWLEDGE_PHRONESIS.md), [GraphRAG](../../Docs/VECTOR_HNSW_GRAPHRAG.md) e [exemplo de IA local](../academico_api_ia-Example/README.md).
