# Automações nativas do NexusDB

Use `POST /db/admin/automation` com os cabeçalhos `X-User`, `X-Pass` e `X-Database`. O usuário precisa ter o papel global `admin`. Cada banco possui suas próprias regras e caixa de saída.

## Gatilho por gravação

Envie este corpo para criar uma regra para nós de teste com o rótulo `Exame`.

```json
{
  "operation": "create",
  "name": "revisar-exame-sintetico",
  "trigger": {"type": "node_written", "label": "Exame"},
  "condition": {"property": "valor", "operator": "gt", "value": 100},
  "action": {"task": "revisar_exame", "message": "Criar tarefa de revisão"},
  "notification": {"recipient": "equipe-revisao", "message": "Tarefa de revisão registrada"}
}
```

Grave, por exemplo, `CREATE (e:Exame {valor: 120})` por `/db/data/cypher`. Cada inserção ou atualização persistida de um nó com o rótulo exato avalia a condição, inclusive quando o valor já atendia ao critério antes da alteração. A primeira regra ativa o diário de recuperação e a persistência SQLite como fonte de verdade para o banco. A tarefa e a confirmação são gravadas na mesma transação da alteração.

A condição é opcional. Use uma propriedade de primeiro nível e `eq` para igualdade de escalares JSON ou `gt`, `gte`, `lt`, `lte` para comparação numérica. Uma propriedade ausente nunca satisfaz a condição.

### Disparo ao entrar na condição

Use `"trigger": {"type": "node_condition_entered", "label": "Exame"}` com a mesma condição do exemplo. A regra compara o estado do nó antes da transação com o estado final. Ela gera uma tarefa se um nó novo já satisfizer a condição ou se um nó existente passar a satisfazê-la. Por exemplo, `98 → 120` dispara, `120 → 125` mantém o alerta existente e `120 → 98 → 120` em transações separadas permite outro disparo no retorno a 120. Várias alterações ao mesmo nó em uma transação são avaliadas pelo resultado final. Uma transação revertida também reverte a tarefa.

As regras existentes com `node_written` seguem avaliando cada gravação.

## Gatilho por horário

Para um lembrete associado a um nó existente, substitua o gatilho do exemplo por:

```json
{"type":"at","at":"2026-11-09T08:30:00-03:00","node_id":123}
```

Use uma data RFC 3339 com `Z` ou um deslocamento explícito, como `-03:00`. Também é possível informar uma hora local sem deslocamento e um fuso regional separado, como `{"type":"at","at":"2026-11-09T08:30:00","timezone":"America/Sao_Paulo"}`. Integrações existentes podem continuar enviando `unix_ms` como alternativa a `at`.

O servidor verifica os agendamentos aproximadamente a cada segundo e processa até 100 vencidos por banco a cada ciclo. Cada regra é avaliada uma vez, inclusive se vencer durante uma parada. Se houver condição, o servidor lê as propriedades atuais do nó indicado. Se a condição falhar ou o nó indicado não existir, a regra passa para `skipped`. Para uma tarefa sem nó associado, omita `node_id` e a condição.

Use `max_delay_ms` no gatilho `at` para definir o atraso máximo após o horário marcado. Por exemplo, `"max_delay_ms": 900000` permite até 15 minutos de atraso. Após esse limite, o agendamento passa para `expired` e nenhuma tarefa entra na caixa de saída. Sem esse campo, o servidor avalia o agendamento vencido quando puder processá-lo, inclusive após reiniciar.

## Login e inicialização

Use `{"type":"login","username":"ana"}` para executar uma tarefa após um login explícito e bem-sucedido via `POST /cluster/login` no banco selecionado. Omita `username` para cobrir todos os usuários com acesso ao banco. A caixa de saída registra o nome do usuário. A autenticação rotineira das demais requisições e as tentativas rejeitadas não disparam a regra.

Use `{"type":"database_started"}` para executar a tarefa na próxima inicialização do servidor, após o banco ter sido carregado com sucesso. O cadastro feito enquanto o servidor está rodando tem efeito na próxima inicialização. Os dois gatilhos usam os mesmos objetos `action` e `notification` do primeiro exemplo e não recebem condição de nó.

## Agendas recorrentes

Para rodar toda segunda-feira às 08h30 no horário de São Paulo, use:

```json
{
  "type": "recurring",
  "frequency": "weekly",
  "start_at": "2026-11-09T08:30:00",
  "timezone": "America/Sao_Paulo"
}
```

As frequências são `daily`, `weekly` e `monthly`. Com fuso regional, o agendador conserva o horário local mesmo quando o deslocamento UTC muda. Se uma ocorrência futura cair em um horário inexistente, ela é pulada. Se o horário ocorrer duas vezes, vale a primeira. O cadastro exige um horário inicial inequívoco.

Um `start_at` RFC 3339 sem o campo `timezone` usa o deslocamento fixo indicado na data. O campo legado `start_unix_ms` continua usando calendário UTC. Envie apenas uma das formas. A agenda mensal conserva o dia original e usa o último dia nos meses mais curtos.

Depois de uma parada, o agendador avalia apenas a ocorrência vencida mais recente e calcula a próxima. `max_delay_ms` pode expirar essa ocorrência, e a próxima continua agendada. Assim como em `at`, `node_id` e `condition` permitem verificar o estado atual de um nó. Em `list`, `next_run_at` mostra a próxima execução em formato legível, `due_ms` mantém o horário numérico e `scheduled_status` mostra o resultado da última avaliação. A caixa de saída identifica a ocorrência por `scheduled_for_ms` e exibe o mesmo instante em UTC no campo `scheduled_at`.

## Auditoria de propriedades

Use `{"type":"property_changed","label":"Exame","property":"valor"}` para monitorar uma propriedade de primeiro nível do nó. A regra registra valores anterior e novo quando a propriedade é adicionada, removida ou alterada em um nó existente. A comparação usa o estado anterior à transação e o estado final. A condição opcional avalia o estado final. O log e a tarefa são gravados na mesma transação que modifica o nó.

Consulte os logs com `{"operation":"audit","after_id":0}`. Cada registro contém a regra, o nó, a propriedade, o horário, `old_value` e `new_value`. Os campos `old_present` e `new_present` distinguem ausência de valor `null`. A caixa de saída referencia o log por `audit_id`. A consulta exige administrador global. Monitore apenas propriedades cujos valores devam ser preservados em histórico.

## Consulta e cancelamento

| Corpo da requisição | Resultado |
| --- | --- |
| `{"operation":"list","after_id":0}` | Lista regras e mostra o estado dos agendamentos (`pending`, `executed`, `skipped` ou `expired`). |
| `{"operation":"outbox","after_id":0}` | Lista tarefas registradas e suas confirmações, incluindo o destinatário informado. |
| `{"operation":"audit","after_id":0}` | Lista logs de alterações de propriedades monitoradas. |
| `{"operation":"delete","id":1}` | Remove a regra e cancela um agendamento pendente. Preserva as entradas já registradas. |

As consultas retornam até 100 itens por página em ordem de ID. Passe `next_after_id` como `after_id` na próxima requisição. Um integrador pode guardar o cursor após processar as entradas e usar o ID da entrada para deduplicar entregas.

A ação nativa registra a tarefa na caixa de saída persistente do banco. O destinatário é um identificador para o consumidor da API. Envio de e-mail, webhook e execução de relatórios exigem integração externa. O recurso funciona em servidor único com bancos que aceitam gravação. A caixa de saída persiste entre reinícios e permanece no SQLite. A exportação lógica do grafo não inclui regras, caixa de saída e logs de auditoria.
