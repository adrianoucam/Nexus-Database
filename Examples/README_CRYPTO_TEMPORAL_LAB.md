# Laboratório didático: mercados em grafos temporais

`crypto_temporal_lab.py` abre uma janela Python/Tkinter para investigar
quem concentra o volume negociado, quando isso ocorre e em quais mercados.
Usa **somente a biblioteca padrão do Python e o NexusDB**, sem pip,
pandas, NetworkX, Streamlit, Arrow ou navegador.

Referências: [notícia da Queen Mary University](https://www.qmul.ac.uk/eecs/news-and-events/news/items/eecs-researchers-uncover-the-hidden-patterns-behind-a-35-billion-cryptocurrency-collapse-.html)
e [artigo dos pesquisadores](https://arxiv.org/abs/2407.10614).
O artigo emprega análise temporal multicamada e examina sinais anômalos,
interconexões e mudanças entre camadas. Este laboratório é uma abordagem
didática própria inspirada nessa classe de problema, **não uma reprodução
do estudo ou uma análise factual do colapso Terra/LUNA**.

## Executar

O executável NexusDB deve existir em target/debug. Se necessário:

```bat
cd /d E:\nexusdb
cargo build --bin nexusdb
cd examples
py crypto_temporal_lab.py
```

O Python padrão instalado no Windows inclui Tkinter/Tcl/Tk. O programa foi
validado com `C:\Python314\python.exe`. Um runtime Python mínimo sem arquivos
Tcl não abre a tela; use seu Python padrão ou `--headless`.

O caminho padrão do servidor independe da pasta atual. Alternativa:

```bat
py crypto_temporal_lab.py --server E:\nexusdb\target\debug\nexusdb.exe --seed 42 --output crypto-temporal-output
```

O programa cria um diretório run-... novo, usa uma porta livre e senha
aleatória e mantém seu próprio NexusDB ativo enquanto a janela estiver aberta.
Ao fechar, termina somente esse processo. Não utiliza o serviço instalado,
não altera databases existentes e não publica dados.

## Roteiro para demonstrar em aula

1. Clique em **1 · Mercado normal**. Veja o volume distribuído entre
   carteiras, HHI baixo e ausência da combinação de sinais.
2. Clique em **2 · Concentração simulada**. Na hora 8, seis carteiras
   concentram aproximadamente 98,6% do volume UST. Compare os valores no
   ranking, as arestas grossas e os horários das operações.
3. Clique numa carteira, linha do ranking ou ligação. A tabela mostra os
   eventos daquela seleção, recuperados do NexusDB. Dê dois cliques num
   evento para abrir seus campos completos, ID da relação e system_at.
4. Clique em **3 · Comparar USDC**: mesmo horário, outra camada. A
   combinação não aparece nesse mercado de controle.
5. Selecione várias moedas. As cores representam camadas; a sobreposição
   Jaccard compara conjuntos de traders ativos, não correlação de preços.
6. Mova o controle de horário ou clique no gráfico. A seleção consulta
   novamente a janela/camadas no NexusDB. Experimente durações de 1, 2 e 4
   horas: o agregado pode esconder sinais presentes numa janela curta.
7. Na hora 10, seis carteiras do conjunto simulado deixam UST e passam a
   USDC. A tela informa a mudança entre camadas, sem atribuir causa.
8. Clique em **Explicar indicadores** e **Salvar relatório** para discutir
   fórmulas, limiares, consultas e evidências.

No gráfico inferior, azul é a participação dos seis maiores; dourado é o
preço mediano UST em USD, usando um eixo separado. Os preços também são
simulados. A queda foi definida no gerador e ocorre nos controles: não é
estimada a partir dos sinais nem demonstra efeito causal das negociações.

## Controles didáticos

Feche a janela e compare outras situações:

```bat
py crypto_temporal_lab.py --scenario independent
py crypto_temporal_lab.py --scenario whale
py crypto_temporal_lab.py --scenario synchronized_small
```

| Cenário | Construção | Interpretação |
|---|---|---|
| coordinated | Seis carteiras com volumes grandes similares e horários alinhados | Combinação exploratória sinalizada |
| independent | Mesmos volumes grandes, horários independentes | Concentração sem alinhamento suficiente |
| whale | Grande volume numa carteira | Concentração não equivale a coordenação entre seis participantes |
| synchronized_small | Seis carteiras alinhadas com volume pequeno | O padrão pequeno não domina o ranking por volume |

O detector examina os **seis maiores por volume**; não encontra todos os
grupos de carteiras sincronizadas e não identifica pessoas. Uma entidade
pode controlar várias carteiras; exchanges/pools agregam operações de outras
pessoas. Arbitragem, bots, notícias e estratégias legítimas são explicações
alternativas. O programa não identifica shorting, intenção ou responsáveis
pelo colapso.

## Modelo e divisão de trabalho

Cada nó representa uma carteira ou contraparte. Cada relação TRADE
representa uma negociação normalizada, com um trader de referência,
BUY/SELL, volume nocional em **centavos de USD**, mercado, preço opcional e
timestamp. Camadas: UST, USDC e DAI no simulador.

O evento é modelado com `[timestamp_ms, timestamp_ms+1)`, isto é, um
intervalo de 1 ms. Isso permite filtrá-lo pela janela temporal, sem tratar
uma negociação como vínculo permanente. As relações são paralelas e têm
event_id distintos.

O **NexusDB** persiste os nós/relações, registra histórico por database,
cria checkpoint e filtra janelas/camadas. A leitura usa
graphRAG.temporalRetrieve com sementes explícitas, sem vetores ou LLM,
para obter relações e propriedades do snapshot histórico.

O **Python** calcula os indicadores e desenha a tela. A linha histórica é
agregada de uma leitura completa do NexusDB; a seleção interativa consulta
o banco novamente. O gerador não é utilizado como fonte oculta das métricas.
A validação compara IDs, timestamps, valores, atores, endpoints e preços
após recuperar os dados persistidos.

## Indicadores e interpretação

- Participação: volume de cada trader / volume total da seleção.
- HHI: soma das participações ao quadrado. Aqui a escala é 0..1.
- Traders efetivos: 1/HHI. Não é uma contagem de pessoas.
- Entropia de Shannon: diversidade das participações, com log natural.
- CV dos top 6: desvio padrão populacional / volume médio; volumes
  semelhantes produzem CV pequeno.
- Sincronismo: média das similaridades cosseno entre histogramas dos seis
  traders em 60 subintervalos da janela. Ao alterar a duração da janela,
  a resolução dos subintervalos também muda.
- Teste exploratório: 199 deslocamentos circulares independentes dos
  histogramas, preservando contagem e estrutura de cada trader e removendo
  o alinhamento entre eles. p = (1 + simulações ≥ observado)/(1 + 199).
- Saldo de vendas: nocional SELL menos BUY do trader declarado; não é saldo
  de carteira, lucro, capital retirado nem identificação de posição short.
- Jaccard de camadas: tamanho da interseção / tamanho da união dos conjuntos
  de traders ativos. Mudança entre camadas registra saída e entrada de
  atividade entre duas janelas consecutivas de uma hora.

O sinal didático combina top6 ≥80%, HHI ≥0,10, CV ≤0,15, sincronismo ≥0,80,
ao menos 3 operações por trader e p ≤0,05. Não são limiares extraídos do
artigo ou calibrados para uso regulatório. O p é condicionado aos top 6 e
à janela; não há correção de múltiplas comparações, validação fora da
amostra ou um modelo nulo do mercado completo. Preço e volume não provam
coordenação ou causalidade. Amostra insuficiente é apresentada explicitamente.

## Utilizar CSV próprio

```bat
py crypto_temporal_lab.py --csv minhas_negociacoes.csv
```

Colunas:

```csv
event_id,timestamp,asset,from,to,trader,side,usd_cents,price_usd
exemplo-1,2022-05-07T08:10:00.000Z,UST,CarteiraA,PoolUST,CarteiraA,SELL,1000000,0.92
```

price_usd é opcional. Datas exigem fuso e precisão máxima de milissegundos;
usd_cents é inteiro positivo, sem arredondamento pelo programa. event_id
deve ser único. O trader deve ser um dos endpoints. O volume de cada
negociação é contado **uma vez**, atribuído ao trader declarado, sem contar
a contraparte novamente. Não forneça as duas pernas do mesmo swap como
negociações separadas, nem some unidades de tokens diferentes como USD.

O laboratório não coleta/decodifica a blockchain. A normalização de swaps,
conversão para nocional USD, classificação BUY/SELL, tratamento de taxas,
duplicatas e identificação de pools precisam ser feitos antes de importar.
Identificadores são tratados como strings exatas; não há clustering de
endereços ou inferência de pessoas. CSV importado não recebe a validação de
verdade-terreno dos cenários simulados.

Limites do exemplo: 5.000 eventos, 100 endpoints, 6 camadas e 7 dias. Uma
leitura truncada retorna erro antes de calcular resultados incompletos.
É um laboratório local, não um benchmark de escala blockchain.

## Arquivos e validação

- transactions.csv: conjunto normalizado utilizado.
- report.json: métricas por hora/camada, seleção atual, checks e movimentos.
- queries.json: argumentos reais dos procedimentos, sem credenciais.
- server.log e data/: pertencem somente à instância isolada.

```bat
py crypto_temporal_lab.py --headless
py -m unittest discover -s ..\tests -p test_crypto_temporal_lab.py -v
```

Na validação local passaram seis testes matemáticos/CSV, as quatro execuções
com NexusDB, a importação CSV e o preenchimento de grafo, ranking e evidências
no Tkinter. Na simulação seed 42, há 696 negociações. O cenário coordenado
teve HHI aproximadamente 0,162, top6 aproximadamente 98,6% e sincronismo 0,80;
o controle independente teve concentração semelhante e sincronismo 0,074.
