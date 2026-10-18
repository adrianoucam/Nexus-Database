# Criar credenciais e testar autenticação

O NexusDB atual autentica por usuário e senha nos cabeçalhos X-User e X-Pass; X-Database escolhe o banco. Atribuir `$env:NEXUSDB_API_TOKEN = 'SEU_TOKEN'` não cria um token, não modifica o servidor e não concede acesso. Authorization Bearer não foi implementado.

Use um usuário já cadastrado com READ no database escolhido. O programa usa somente Python padrão, executa leitura e não mostra credenciais:

```powershell
cd E:\nexusdb
$env:NEXUSDB_URL = 'http://127.0.0.1:7474'
$env:NEXUSDB_DATABASE = 'neo4j' # ajuste para um banco existente
$credencialNexus = Get-Credential -UserName 'admin' -Message 'Credenciais atuais do NexusDB'
$env:NEXUSDB_USER = $credencialNexus.UserName
$env:NEXUSDB_PASSWORD = $credencialNexus.GetNetworkCredential().Password
py examples/authentication_test.py
Remove-Item Env:NEXUSDB_PASSWORD
```

Resultado esperado: credenciais corretas aceitas; senha inválida rejeitada com 401; Bearer isolado rejeitado com 401. URL/USER/PASSWORD/DATABASE são lidos por esse programa cliente, não novas configurações de autenticação do servidor. Para conexão remota, a URL deve usar HTTPS.

Se precisar criar um usuário, um administrador autenticado utiliza os endpoints existentes `POST /db/admin/user/create` (username/password/role=user/expires_days) e `POST /db/admin/grant` (username/database/access=READ). WRITE, quando necessário, precisa ser concedido separadamente. Não gere um usuário admin apenas para leitura.

`NEXUSDB_ADMIN_PASSWORD` configura o bootstrap de uma instalação/data root novo; não use essa variável como mecanismo de redefinir a senha de usuários já cadastrados. A senha atual deve vir do cadastro existente.

Para databases com `knowledge.initialize`, usuários comuns precisam usar consultas com escopo; `RETURN 1 AS teste` pode ser bloqueado pela política. Nesse caso, execute a demonstração isolada de conhecimento para testar a autenticação, ou use uma chamada `knowledge.search` autorizada no cliente apropriado.

Licença: [LICENSE](../LICENSE).

## Gateway REST opcional

O novo [gateway Rust/Axum](../crates/nexusdb-rest-gateway/README.md), na porta
8787 por padrão, aceita X-API-Key e Bearer com chaves próprias temporárias.
A porta nativa 7474 mantém a autenticação descrita acima. NEXUSDB_API_TOKEN
pode guardar uma chave gerada pelo gateway no cliente; ela precisa ser enviada
no cabeçalho de uma requisição ao gateway, não ao servidor nativo.
