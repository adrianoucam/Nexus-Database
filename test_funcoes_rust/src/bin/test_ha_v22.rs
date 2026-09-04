use nexusdb::execution::{
    Condition, EdgeKind, ExecutionEdge, ExecutionGraph, ExecutionNode, ExecutorRegistry, GateRule,
    GraphLayer, NodeExecutor, NodeKind, NodeResult, NodeStatus,
};
use nexusdb::model::NexusDB;
use serde_json::{json, Value};
use std::env;
use std::process;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Barrier};
use std::thread;
use std::time::Duration;
use uuid::Uuid;

struct TestResult {
    name: String,
    ok: bool,
    details: String,
    warning: bool,
}

struct EchoExecutor;

impl NodeExecutor for EchoExecutor {
    fn execute(&self, node: &ExecutionNode) -> Result<NodeResult, String> {
        Ok(NodeResult {
            output: node.input.clone(),
            evidence_details: json!({"executor": "echo", "node": node.id}),
        })
    }
}

struct FailOnceExecutor {
    calls: AtomicUsize,
}

impl NodeExecutor for FailOnceExecutor {
    fn execute(&self, _node: &ExecutionNode) -> Result<NodeResult, String> {
        if self.calls.fetch_add(1, Ordering::SeqCst) == 0 {
            Err("schema inválido: campo tipo ausente".to_string())
        } else {
            Ok(NodeResult {
                output: json!({"tipo": "resultado", "ok": true}),
                evidence_details: json!({"correction_applied": true}),
            })
        }
    }
}

struct ParallelProbeExecutor {
    barrier: Arc<Barrier>,
    active: Arc<AtomicUsize>,
    max_active: Arc<AtomicUsize>,
}

impl NodeExecutor for ParallelProbeExecutor {
    fn execute(&self, node: &ExecutionNode) -> Result<NodeResult, String> {
        let active = self.active.fetch_add(1, Ordering::SeqCst) + 1;
        self.max_active.fetch_max(active, Ordering::SeqCst);
        self.barrier.wait();
        thread::sleep(Duration::from_millis(10));
        self.active.fetch_sub(1, Ordering::SeqCst);
        Ok(NodeResult {
            output: json!({"node": node.id}),
            evidence_details: json!({"parallel": true}),
        })
    }
}

fn edge(from: &str, to: &str, kind: EdgeKind, condition: Condition) -> ExecutionEdge {
    ExecutionEdge {
        from: from.to_string(),
        to: to.to_string(),
        kind,
        condition,
    }
}

fn run_execution_graph_cases() -> Vec<TestResult> {
    let mut results = Vec::new();
    let mut case = |name: &str, test: &dyn Fn() -> Result<String, String>| match test() {
        Ok(details) => results.push(TestResult {
            name: format!("ExecutionGraph: {name}"),
            ok: true,
            details,
            warning: false,
        }),
        Err(details) => results.push(TestResult {
            name: format!("ExecutionGraph: {name}"),
            ok: false,
            details,
            warning: false,
        }),
    };

    case("tipos, arestas e três camadas", &|| {
        let kinds = [
            NodeKind::Splitter,
            NodeKind::Worker,
            NodeKind::Code,
            NodeKind::Gate,
            NodeKind::Human,
        ];
        let layers = [
            GraphLayer::Data,
            GraphLayer::Knowledge,
            GraphLayer::Execution,
        ];
        let edge_kinds = [
            EdgeKind::Dependency,
            EdgeKind::Correction,
            EdgeKind::Learning,
            EdgeKind::Approval,
        ];
        let encoded =
            serde_json::to_value((&kinds, &layers, &edge_kinds)).map_err(|e| e.to_string())?;
        let text = encoded.to_string();
        for expected in [
            "splitter",
            "worker",
            "code",
            "gate",
            "human",
            "dependency",
            "correction",
            "learning",
            "approval",
            "data",
            "knowledge",
            "execution",
        ] {
            if !text.contains(expected) {
                return Err(format!("tipo serializado ausente: {expected}"));
            }
        }
        Ok(text)
    });

    case("condição por JSON Pointer e status", &|| {
        let mut registry = ExecutorRegistry::default();
        registry.register("worker", Arc::new(EchoExecutor));
        let mut graph = ExecutionGraph::new("conditional");
        graph.add_node(ExecutionNode::new(
            "source",
            NodeKind::Worker,
            json!({"route": "approved"}),
        ))?;
        graph.add_node(ExecutionNode::new(
            "target",
            NodeKind::Worker,
            json!({"work": true}),
        ))?;
        graph.add_node(ExecutionNode::new(
            "exists-target",
            NodeKind::Worker,
            json!({"work": "exists"}),
        ))?;
        graph.add_node(ExecutionNode::new(
            "status-target",
            NodeKind::Worker,
            json!({"work": "status"}),
        ))?;
        graph.add_edge(edge(
            "source",
            "target",
            EdgeKind::Dependency,
            Condition::OutputEquals {
                pointer: "/route".to_string(),
                value: json!("approved"),
            },
        ))?;
        graph.add_edge(edge(
            "source",
            "exists-target",
            EdgeKind::Dependency,
            Condition::OutputExists {
                pointer: "/route".to_string(),
            },
        ))?;
        graph.add_edge(edge(
            "source",
            "status-target",
            EdgeKind::Dependency,
            Condition::SourceSucceeded,
        ))?;
        let report = graph.run(&registry)?;
        if report.waves
            != vec![
                vec!["source".to_string()],
                vec![
                    "exists-target".to_string(),
                    "status-target".to_string(),
                    "target".to_string(),
                ],
            ]
        {
            return Err(format!("ondas inesperadas: {:?}", report.waves));
        }
        Ok(format!("ondas={:?}", report.waves))
    });

    case("ready_nodes e paralelismo por ondas", &|| {
        let active = Arc::new(AtomicUsize::new(0));
        let max_active = Arc::new(AtomicUsize::new(0));
        let mut registry = ExecutorRegistry::default();
        registry.register(
            "worker",
            Arc::new(ParallelProbeExecutor {
                barrier: Arc::new(Barrier::new(2)),
                active: active.clone(),
                max_active: max_active.clone(),
            }),
        );
        let mut graph = ExecutionGraph::new("parallel");
        graph.add_node(ExecutionNode::new("a", NodeKind::Worker, Value::Null))?;
        graph.add_node(ExecutionNode::new("b", NodeKind::Worker, Value::Null))?;
        if graph.ready_nodes() != vec!["a".to_string(), "b".to_string()] {
            return Err(format!("ready_nodes incorreto: {:?}", graph.ready_nodes()));
        }
        let report = graph.run(&registry)?;
        if max_active.load(Ordering::SeqCst) < 2 {
            return Err("os executores independentes não se sobrepuseram".to_string());
        }
        Ok(format!(
            "ondas={:?}, max_active={}",
            report.waves,
            max_active.load(Ordering::SeqCst)
        ))
    });

    case("retry, evidências e restrição aprendida", &|| {
        let mut registry = ExecutorRegistry::default();
        registry.register(
            "worker",
            Arc::new(FailOnceExecutor {
                calls: AtomicUsize::new(0),
            }),
        );
        let mut node = ExecutionNode::new(
            "agent",
            NodeKind::Worker,
            json!({
                "suggested_constraint": "preserve argumentos-chave = true"
            }),
        );
        node.max_attempts = 2;
        let mut graph = ExecutionGraph::new("retry-learning");
        graph.add_node(node)?;
        let report = graph.run(&registry)?;
        let node = &graph.nodes["agent"];
        if node.status != NodeStatus::Succeeded || node.attempts != 2 || node.evidence.len() != 2 {
            return Err(format!(
                "estado/tentativas/evidências inválidos: {:?}",
                node
            ));
        }
        if node.evidence[0].success || !node.evidence[1].success || report.learned_constraints != 1
        {
            return Err(format!(
                "proveniência/aprendizado inválidos: {:?}",
                node.evidence
            ));
        }
        Ok(format!(
            "attempts={}, constraint={}",
            node.attempts, graph.constraints.constraints[0].rule
        ))
    });

    case("gates ExitCode, JSON Schema e testes", &|| {
        let mut graph = ExecutionGraph::new("deterministic-gates");
        let mut exit = ExecutionNode::new("exit", NodeKind::Gate, json!({"exit_code": 0}));
        exit.gate = Some(GateRule::ExitCode { expected: 0 });
        let mut schema = ExecutionNode::new("schema", NodeKind::Gate, json!({"tipo": "ok"}));
        schema.gate = Some(GateRule::JsonSchema {
            schema: json!({
                "type": "object", "required": ["tipo"], "properties": {"tipo": {"type": "string"}}
            }),
        });
        let mut tests = ExecutionNode::new("tests", NodeKind::Gate, json!({"tests_passed": true}));
        tests.gate = Some(GateRule::TestsPassed);
        graph.add_node(exit)?;
        graph.add_node(schema)?;
        graph.add_node(tests)?;
        let report = graph.run(&ExecutorRegistry::default())?;
        if report.succeeded.len() != 3 || graph.nodes.values().any(|n| n.evidence.len() != 1) {
            return Err(format!("gates não ficaram verdes: {report:?}"));
        }
        Ok(format!("gates verdes={:?}", report.succeeded))
    });

    case("gate vermelho registra evidência", &|| {
        let mut graph = ExecutionGraph::new("red-gate");
        let mut gate = ExecutionNode::new("exit", NodeKind::Gate, json!({"exit_code": 7}));
        gate.gate = Some(GateRule::ExitCode { expected: 0 });
        graph.add_node(gate)?;
        let report = graph.run(&ExecutorRegistry::default())?;
        let evidence = &graph.nodes["exit"].evidence[0];
        if report.failed != vec!["exit".to_string()]
            || evidence.reason != "gate_red"
            || evidence.success
        {
            return Err(format!("evidência de falha inválida: {evidence:?}"));
        }
        Ok(format!(
            "reason={}, details={}",
            evidence.reason, evidence.details
        ))
    });

    case("Human e HumanApproval retomáveis", &|| {
        let mut graph = ExecutionGraph::new("human");
        graph.add_node(ExecutionNode::new(
            "human-node",
            NodeKind::Human,
            json!({"question": "aprovar?"}),
        ))?;
        let first = graph.run(&ExecutorRegistry::default())?;
        if first.waiting_human != vec!["human-node".to_string()] {
            return Err(format!("espera inválida: {first:?}"));
        }
        graph.approve("human-node", true, json!({"reviewer": "qa"}))?;

        let mut gate_graph = ExecutionGraph::new("human-gate");
        let mut gate = ExecutionNode::new("approval", NodeKind::Gate, Value::Null);
        gate.gate = Some(GateRule::HumanApproval);
        gate_graph.add_node(gate)?;
        gate_graph.run(&ExecutorRegistry::default())?;
        gate_graph.approve("approval", false, json!({"reviewer": "qa"}))?;
        if graph.nodes["human-node"].status != NodeStatus::Succeeded
            || gate_graph.nodes["approval"].status != NodeStatus::Failed
        {
            return Err("decisões humanas não foram persistidas no estado".to_string());
        }
        Ok("aprovação e rejeição humanas registradas".to_string())
    });

    case("registro desacoplado por nome e tipo", &|| {
        let mut registry = ExecutorRegistry::default();
        registry.register("splitter", Arc::new(EchoExecutor));
        registry.register("code", Arc::new(EchoExecutor));
        registry.register("llm-custom", Arc::new(EchoExecutor));
        let mut graph = ExecutionGraph::new("registry");
        graph.add_node(ExecutionNode::new(
            "split",
            NodeKind::Splitter,
            json!({"parts": 2}),
        ))?;
        graph.add_node(ExecutionNode::new(
            "code",
            NodeKind::Code,
            json!({"script": "safe-adapter"}),
        ))?;
        graph.add_node(ExecutionNode::new(
            "llm",
            NodeKind::Worker,
            json!({"executor": "llm-custom"}),
        ))?;
        let report = graph.run(&registry)?;
        if report.succeeded.len() != 3 {
            return Err(format!("dispatch incompleto: {report:?}"));
        }
        Ok(format!("despachados={:?}", report.succeeded))
    });

    case("arestas de correção e ciclos permitidos", &|| {
        let mut registry = ExecutorRegistry::default();
        registry.register("code", Arc::new(EchoExecutor));
        let mut graph = ExecutionGraph::new("correction-cycle");
        graph.add_node(ExecutionNode::new("a", NodeKind::Worker, Value::Null))?;
        graph.add_node(ExecutionNode::new("b", NodeKind::Worker, Value::Null))?;
        graph.add_node(ExecutionNode::new("failed", NodeKind::Worker, Value::Null))?;
        graph.add_node(ExecutionNode::new(
            "fixer",
            NodeKind::Code,
            json!({"correction": true}),
        ))?;
        graph.add_edge(edge(
            "a",
            "b",
            EdgeKind::Correction,
            Condition::SourceFailed,
        ))?;
        graph.add_edge(edge(
            "b",
            "a",
            EdgeKind::Correction,
            Condition::SourceFailed,
        ))?;
        graph.add_edge(edge(
            "failed",
            "fixer",
            EdgeKind::Correction,
            Condition::SourceFailed,
        ))?;
        let report = graph.run(&registry)?;
        if graph.nodes["failed"].status != NodeStatus::Failed
            || graph.nodes["fixer"].status != NodeStatus::Succeeded
        {
            return Err(format!("caminho de correção não foi ativado: {report:?}"));
        }
        Ok(format!(
            "correção ativada e ciclo exclusivamente de correção aceito; ondas={:?}",
            report.waves
        ))
    });

    case("ciclo de dependência rejeitado", &|| {
        let mut graph = ExecutionGraph::new("invalid-cycle");
        graph.add_node(ExecutionNode::new("a", NodeKind::Worker, Value::Null))?;
        graph.add_node(ExecutionNode::new("b", NodeKind::Worker, Value::Null))?;
        graph.add_edge(edge("a", "b", EdgeKind::Dependency, Condition::Always))?;
        graph.add_edge(edge("b", "a", EdgeKind::Dependency, Condition::Always))?;
        match graph.run(&ExecutorRegistry::default()) {
            Err(message) if message.contains("ciclo de dependência") => Ok(message),
            other => Err(format!("ciclo deveria ser rejeitado: {other:?}")),
        }
    });

    case("fachada NexusDB: put/get/run/approve", &|| {
        let data_root = env::temp_dir().join(format!("nexusdb_execution_test_{}", Uuid::new_v4()));
        env::set_var("NEXUSDB_MODE", "SINGLE");
        env::set_var("NEXUSDB_DATA_ROOT", &data_root);
        env::set_var("NEXUSDB_ADMIN_PASSWORD", "Execution-Test-Admin-123!");
        let db = NexusDB::new()?;
        let mut graph = ExecutionGraph::new("facade");
        graph.add_node(ExecutionNode::new("review", NodeKind::Human, Value::Null))?;
        db.put_execution_graph(graph)?;
        if db.get_execution_graph("facade")?.is_none() {
            return Err("put/get não preservou o grafo".to_string());
        }
        let report = db.run_execution_graph("facade", &ExecutorRegistry::default())?;
        if report.waiting_human != vec!["review".to_string()] {
            return Err(format!("run inválido: {report:?}"));
        }
        db.approve_execution_node("facade", "review", true, json!({"by": "integration-test"}))?;
        let saved = db
            .get_execution_graph("facade")?
            .ok_or_else(|| "grafo desapareceu".to_string())?;
        if saved.nodes["review"].status != NodeStatus::Succeeded {
            return Err("approve não atualizou o nó".to_string());
        }
        Ok(format!("catálogo validado em {}", data_root.display()))
    });

    results
}

#[derive(Clone)]
struct NexusTestRunner {
    nodes: Vec<String>,
    user: String,
    pass: String,
    database: String,
    verbose: bool,
}

impl NexusTestRunner {
    fn new() -> Result<Self, String> {
        let nodes_env = env::var("NEXUSDB_NODES").unwrap_or_else(|_| {
            "http://127.0.0.1:7474,http://127.0.0.1:7475,http://127.0.0.1:7476".to_string()
        });
        let nodes: Vec<String> = nodes_env
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();

        if nodes.is_empty() {
            return Err("NEXUSDB_NODES não contém nenhum endereço válido.".to_string());
        }

        let user = env::var("NEXUSDB_TEST_ADMIN_USER").unwrap_or_else(|_| "admin".to_string());
        let pass = env::var("NEXUSDB_TEST_ADMIN_PASSWORD")
            .or_else(|_| env::var("NEXUSDB_PASSWORD"))
            .map_err(|_| {
                "Defina NEXUSDB_TEST_ADMIN_PASSWORD (ou NEXUSDB_PASSWORD) antes de executar o teste; a senha não é mais fixa no código."
                    .to_string()
            })?;

        Ok(Self {
            nodes,
            user,
            pass,
            database: env::var("NEXUSDB_TEST_DATABASE").unwrap_or_else(|_| "teste_db".to_string()),
            verbose: true,
        })
    }

    fn post(&self, node: &str, path: &str, payload: &Value) -> Result<Value, String> {
        let url = format!("{}{}", node, path);
        if self.verbose {
            println!(
                "[DEBUG] Tentando acessar o servidor -> POST {} | Payload size: {} bytes",
                url,
                payload.to_string().len()
            );
        }

        let body_string = payload.to_string();

        let resp = ureq::post(&url)
            .set("X-User", &self.user)
            .set("X-Pass", &self.pass)
            .set("X-Database", &self.database)
            .set("Content-Type", "application/json")
            .send_string(&body_string);

        match resp {
            Ok(response) => {
                let body_text = response.into_string().map_err(|e| e.to_string())?;
                if self.verbose {
                    println!("[DEBUG] Sucesso na resposta de {}", url);
                }
                let json_res: Value =
                    serde_json::from_str(&body_text).map_err(|e| e.to_string())?;
                Ok(json_res)
            }
            Err(ureq::Error::Status(code, response)) => {
                let body = response.into_string().unwrap_or_default();
                let err_msg = format!("HTTP Error {}: {}", code, body);
                println!("[WARN] Falha controlada ao acessar {}: {}", url, err_msg);
                Err(err_msg)
            }
            Err(e) => {
                let err_msg = e.to_string();
                println!("[FAIL] Erro de conexão/rede com o nó {}: {}", url, err_msg);
                Err(err_msg)
            }
        }
    }

    fn response_has_application_error(response: &Value) -> bool {
        matches!(
            response.get("status").and_then(Value::as_str),
            Some("error" | "partial_error")
        ) || response
            .get("errors")
            .and_then(Value::as_array)
            .is_some_and(|errors| !errors.is_empty())
    }

    fn cluster_health(&self, node: &str) -> Result<Value, String> {
        let url = format!("{}/cluster/health", node.trim_end_matches('/'));
        let response = ureq::get(&url)
            .timeout(Duration::from_secs(3))
            .call()
            .map_err(|e| format!("{}: {}", node, e))?;
        let body = response.into_string().map_err(|e| e.to_string())?;
        serde_json::from_str(&body).map_err(|e| format!("{}: JSON inválido: {}", node, e))
    }

    fn wait_for_leader(&self, timeout: Duration) -> Result<String, String> {
        let started = std::time::Instant::now();
        let mut last_states = Vec::new();
        while started.elapsed() < timeout {
            last_states.clear();
            for node in &self.nodes {
                match self.cluster_health(node) {
                    Ok(health) => {
                        let role = health.get("role").and_then(Value::as_str).unwrap_or("?");
                        let leader = health.get("leader_id").and_then(Value::as_u64);
                        last_states.push(format!("{} role={} leader_id={:?}", node, role, leader));
                        if role == "LEADER" || leader.is_some() {
                            return Ok(last_states.last().cloned().unwrap_or_default());
                        }
                    }
                    Err(error) => last_states.push(error),
                }
            }
            thread::sleep(Duration::from_millis(500));
        }
        Err(format!(
            "Cluster sem leader após {}s. Estados: {}. Reinicie os três nós pelo run_cluster_ha.bat para garantir o mesmo NEXUSDB_HA_SECRET.",
            timeout.as_secs(),
            last_states.join(" | ")
        ))
    }

    /// Tenta a escrita em todos os membros até encontrar o leader. Respostas
    /// HTTP 200 com `partial_error` também são falhas e não encerram o retry.
    fn post_write(&self, path: &str, payload: &Value) -> Result<Value, String> {
        let mut errors = Vec::new();
        for node in &self.nodes {
            match self.post(node, path, payload) {
                Ok(response) if !Self::response_has_application_error(&response) => {
                    return Ok(response);
                }
                Ok(response) => errors.push(format!("{} retornou {}", node, response)),
                Err(error) => errors.push(format!("{} retornou {}", node, error)),
            }
        }
        Err(format!(
            "Nenhum nó aceitou a escrita em {}: {}",
            path,
            errors.join(" | ")
        ))
    }

    fn cypher(&self, query: &str) -> Result<Value, String> {
        let payload = json!({
            "statements": [{"query": query}]
        });
        self.post_write("/db/data/cypher", &payload)
    }
}

fn main() {
    let admin_runner = match NexusTestRunner::new() {
        Ok(runner) => runner,
        Err(e) => {
            eprintln!("[CRITICAL FAIL] {}", e);
            process::exit(1);
        }
    };
    let run_id = format!("nexus_test_{}", &Uuid::new_v4().to_string()[..10]);
    let mut results: Vec<TestResult> = Vec::new();

    println!("\n=== NexusDB Functional Test HA v22 (Rust Native Debug Mode) ===");
    println!(
        "[DEBUG] Nós configurados no cluster: {:?}",
        admin_runner.nodes
    );
    println!("[DEBUG] Database alvo: {}", admin_runner.database);
    println!("[DEBUG] Run ID gerado: {}\n", run_id);

    match admin_runner.wait_for_leader(Duration::from_secs(15)) {
        Ok(state) => println!("[DEBUG] Leader detectado: {}", state),
        Err(error) => {
            eprintln!("[CRITICAL FAIL] {}", error);
            process::exit(1);
        }
    }

    // 1. Tentativa de conexão e criação do Database
    println!(
        "[DEBUG] Iniciando tentativa de conexão com o primeiro nó ativo para criar o database..."
    );
    let create_db_res = admin_runner.post_write(
        "/db/admin/database/create",
        &json!({"database": admin_runner.database}),
    );

    let db_ok = create_db_res.is_ok();
    if !db_ok {
        println!("[CRITICAL FAIL] Não foi possível conectar ao banco para iniciar os testes. Verifique se o NexusDB está rodando na porta 7474 e se as credenciais estão corretas.");
        process::exit(1);
    }

    results.push(TestResult {
        name: "Criar/Garantir database".to_string(),
        ok: true,
        details: format!("{:?}", create_db_res),
        warning: false,
    });

    // 2. Cria uma conta descartável. O teste nunca altera a senha do admin.
    let test_user = format!("ha_test_{}", &run_id[run_id.len() - 8..]);
    let initial_password = format!("Initial-{}-A9!", Uuid::new_v4());
    let new_password = format!("Changed-{}-B8!", Uuid::new_v4());
    println!("[DEBUG] Criando usuário temporário para testar a troca de senha...");
    let create_user_res = admin_runner.post(
        &admin_runner.nodes[0],
        "/db/admin/user/create",
        &json!({
            "username": test_user,
            "password": initial_password,
            "role": "user",
            "password_expires_days": 1
        }),
    );
    let grant_res = admin_runner.post(
        &admin_runner.nodes[0],
        "/db/admin/grant",
        &json!({
            "username": test_user,
            "database": admin_runner.database,
            "access": ["READ", "WRITE"]
        }),
    );

    let mut runner = admin_runner.clone();
    runner.user = test_user;
    runner.pass = initial_password;

    println!("[DEBUG] Executando troca de senha do usuário temporário...");
    let pwd_res = if create_user_res.is_ok() && grant_res.is_ok() {
        runner.post(
            &runner.nodes[0],
            "/db/auth/password/change",
            &json!({"new_password": new_password}),
        )
    } else {
        Err(format!(
            "Falha preparando usuário temporário: create={:?}, grant={:?}",
            create_user_res, grant_res
        ))
    };
    let pwd_ok = pwd_res.is_ok();

    if pwd_ok {
        println!("[DEBUG] Senha do usuário temporário alterada com sucesso.");
        runner.pass = new_password;
    } else {
        println!("[WARN] Falha ao alterar a senha do usuário temporário.");
    }

    results.push(TestResult {
        name: "Alteração de senha do usuário".to_string(),
        ok: pwd_ok,
        details: format!("{:?}", pwd_res),
        warning: !pwd_ok,
    });

    // 3. Criação de Índices com logs de debug
    for field in &["run_id", "cidade", "person_id"] {
        let q = format!("CREATE INDEX ON :PessoaTeste({})", field);
        println!("[DEBUG] Criando índice para o campo: {}", field);
        let res = admin_runner.cypher(&q);
        let is_ok = res.is_ok();
        if !is_ok {
            println!(
                "[WARN] Aviso: Índice para '{}' retornou falha ou já existe.",
                field
            );
        }
        results.push(TestResult {
            name: format!("Criar índice PessoaTeste({})", field),
            ok: is_ok,
            details: format!("{:?}", res),
            warning: !is_ok,
        });
    }

    // 4. Bulk Create de Nós
    println!("[DEBUG] Executando Bulk Create de nós de teste...");
    let bulk_rows = json!({
        "rows": [
            {"key": "T001", "label": "PessoaTeste", "properties": {"person_id": "T001", "nome": "Ana Teste", "cidade": "niteroi", "empresa": "Nexus Lab", "idade": 31, "run_id": run_id}},
            {"key": "T002", "label": "PessoaTeste", "properties": {"person_id": "T002", "nome": "Bruno Teste", "cidade": "niteroi", "empresa": "Nexus Lab", "idade": 35, "run_id": run_id}},
            {"key": "T003", "label": "PessoaTeste", "properties": {"person_id": "T003", "nome": "Carla Teste", "cidade": "rio de janeiro", "empresa": "UFF", "idade": 28, "run_id": run_id}},
            {"key": "T004", "label": "PessoaTeste", "properties": {"person_id": "T004", "nome": "Diego Teste", "cidade": "sao paulo", "empresa": "USP", "idade": 42, "run_id": run_id}}
        ]
    });

    let bulk_res = admin_runner.post_write("/db/data/node/bulk", &bulk_rows);
    let bulk_ok = bulk_res.is_ok();
    results.push(TestResult {
        name: "Bulk create de nós".to_string(),
        ok: bulk_ok,
        details: format!("{:?}", bulk_res),
        warning: false,
    });

    // 5. Motor nativo de grafos executáveis (não depende do cluster HTTP).
    println!("[DEBUG] Executando testes do motor de Execution Graphs...");
    results.extend(run_execution_graph_cases());

    // Relatório Final Consolidado
    println!("\n=== Resultado dos Testes Nativos em Rust (Com Debug & Auth) ===");
    let mut ok_count = 0;
    let mut fail_count = 0;
    let mut warn_count = 0;

    for r in &results {
        let status = if r.ok {
            if r.warning {
                warn_count += 1;
                "WARN"
            } else {
                ok_count += 1;
                "OK"
            }
        } else {
            fail_count += 1;
            "FAIL"
        };
        println!("[{}] {}", status, r.name);
        if !r.details.is_empty() {
            println!("       Details: {}", r.details);
        }
    }

    println!("\nResumo:");
    println!("  OK   : {}", ok_count);
    println!("  WARN : {}", warn_count);
    println!("  FAIL : {}", fail_count);

    if fail_count > 0 {
        println!("[FAIL] O teste encontrou erros críticos de execução.");
        process::exit(1);
    } else {
        println!("[SUCCESS] Todos os testes passaram, incluindo a troca de senha!");
        process::exit(0);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn execution_graph_functional_suite() {
        let results = run_execution_graph_cases();
        let failures: Vec<_> = results
            .iter()
            .filter(|result| !result.ok)
            .map(|result| format!("{}: {}", result.name, result.details))
            .collect();
        assert!(failures.is_empty(), "{}", failures.join("\n"));
        assert_eq!(results.len(), 11);
    }
}
