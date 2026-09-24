# Usuários, proprietários e permissões

Execute no nexus-cli atualizado, terminando cada comando com `;`, ou envie
`{"statements":[{"query":"SHOW USERS"}]}` ao endpoint `/db/data/cypher`.
As credenciais continuam nos cabeçalhos X-User e X-Pass.

```sql
CREATE USER operador WITH PASSWORD 'substitua-esta-senha' LOGIN;
ALTER USER operador PASSWORD 'outra-senha-exclusiva';
ALTER USER operador NOLOGIN;
ALTER USER operador LOGIN UNLOCK;
ALTER USER operador CREATEDB;
ALTER USER operador NOCREATEDB;
SHOW USERS;

CREATE DATABASE vendas OWNER operador;
CREATE DATABASE estoque WITH OWNER = operador;
ALTER DATABASE vendas OWNER TO admin;
SHOW DATABASES;

GRANT READ ON DATABASE vendas TO operador;
GRANT READ, WRITE ON DATABASE vendas TO operador;
GRANT ALL PRIVILEGES ON DATABASE estoque TO operador;
REVOKE WRITE ON DATABASE vendas FROM operador;
SHOW GRANTS;
SHOW GRANTS FOR operador;

ALTER DATABASE estoque OWNER TO admin;
DROP USER operador;
```

Senhas exigem pelo menos 12 caracteres. Aspas simples dentro da senha são
representadas por duas aspas simples. Comandos de senha não entram no histórico
do CLI atualizado nem no registro de consultas do servidor.

Somente SUPERUSER cria/remove usuários, altera atributos de outras contas e
consulta SHOW USERS ou SHOW GRANTS de terceiros. Qualquer usuário autenticado
pode alterar a própria senha. `ALTER USER nome SUPERUSER` e `NOSUPERUSER` são
restritos a SUPERUSER. O admin de recuperação não pode ser removido ou perder login
e SUPERUSER por estes comandos. A troca de senha também desbloqueia a conta;
reconecte o cliente com a nova senha.

CREATEDB permite criar bancos para si próprio. SUPERUSER pode criá-los para outro
usuário. OWNER tem acesso implícito total e pode transferir propriedade, remover
o banco e conceder/revogar acessos. DROP USER rejeita contas proprietárias de
bancos: transfira OWNER antes. Transferir OWNER não remove concessões explícitas.

READ permite leitura; WRITE permite escrita; ADMIN permite ambas e operações
administrativas do banco, sem tornar o usuário SUPERUSER. GRANT/REVOKE exige
OWNER ou SUPERUSER. REVOKE modifica concessões explícitas, não os direitos
implícitos de OWNER/SUPERUSER. ALL concede READ, WRITE e ADMIN.

## Escopo e compatibilidade

A sintaxe é inspirada no PostgreSQL; privilégios são por banco e usam
READ/WRITE/ADMIN. Não implementa privilégios por tabela, roles herdadas,
SELECT/INSERT, CASCADE ou IF EXISTS. Identificadores aceitam letras ASCII,
números e underscore, até 128 caracteres; nomes de usuários distinguem caixa.
SHOW DATABASES mostra bancos acessíveis e seus proprietários; bancos legados
sem proprietário explícito pertencem ao admin.

O catálogo de usuários, propriedade e concessões é **local a cada nó**.
Estes comandos não são replicados automaticamente pelo HA. Em cluster,
aplique a configuração em cada nó; não envie senhas ao WAL de replicação.
Backups de dados feitos pelo nexus-backup não incluem este catálogo.

Comandos administrativos de uma requisição são executados sequencialmente,
sem transação coletiva. Erros são retornados em `errors` com status
`partial_error`; os comandos anteriores podem já ter sido concluídos.
DDL físico e catálogo de segurança não formam uma única transação distribuída.
