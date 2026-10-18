//! Synthetic hospital validation. Always launches in its own fresh process/data root.
use nexusdb::{
    compute::{Backend, CancellationToken, ExecutionContext},
    graph_routes,
    model::NexusDB,
    temporal_history,
};
use serde_json::{Value, json};
use std::{
    path::PathBuf,
    sync::Arc,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
const DB: &str = "EXAMPLE_TEMPORAL_HOSPITAL";
const BASE: i64 = 1790812800000;
const MINUTE: i64 = 60000;

fn main() {
    if let Err(error) = run() {
        eprintln!("Temporal demo failed: {error}");
        std::process::exit(1);
    }
}
fn run() -> Result<(), String> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let value = |flag: &str| {
        args.iter()
            .position(|a| a == flag)
            .and_then(|i| args.get(i + 1))
            .cloned()
    };
    let patients: usize = value("--patients")
        .unwrap_or("250".into())
        .parse()
        .map_err(|_| "--patients must be integer")?;
    if !(2..=10000).contains(&patients) {
        return Err("--patients must be 2..10000".into());
    }
    let seed: u64 = value("--seed")
        .unwrap_or("42".into())
        .parse()
        .map_err(|_| "--seed must be integer")?;
    if !args.iter().any(|a| a == "--worker") {
        let output = PathBuf::from(value("--output").unwrap_or("temporal-demo-output".into()));
        std::fs::create_dir_all(&output).map_err(|e| e.to_string())?;
        let output = std::fs::canonicalize(output).map_err(|e| e.to_string())?;
        let root = output.join(format!(
            "run-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map_err(|e| e.to_string())?
                .as_nanos()
        ));
        std::fs::create_dir(&root).map_err(|e| e.to_string())?;
        use rand_core::{OsRng, RngCore};
        let mut random = [0u8; 32];
        OsRng.fill_bytes(&mut random);
        let password = random
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect::<String>();
        let status =
            std::process::Command::new(std::env::current_exe().map_err(|e| e.to_string())?)
                .args([
                    "--worker",
                    "--patients",
                    &patients.to_string(),
                    "--seed",
                    &seed.to_string(),
                ])
                .current_dir(&root)
                .env("NEXUSDB_DATA_ROOT", root.join("data"))
                .env("NEXUSDB_MODE", "SINGLE")
                .env("NEXUSDB_ADMIN_PASSWORD", password)
                .env("NEXUSDB_SQLITE_BATCH_SIZE", "1000")
                .env("NEXUSDB_COMPUTE_BACKEND", "CPU_SERIAL")
                .env("NEXUSDB_CUDA_ENABLED", "false")
                .env("NEXUSDB_DEMO_OUTPUT", &root)
                .status()
                .map_err(|e| e.to_string())?;
        if !status.success() {
            return Err("Isolated demo process failed".into());
        }
        println!("Report: {}", root.join("report.json").display());
        println!(
            "Simulated data: {}",
            root.join("simulated_hospital.json").display()
        );
        return Ok(());
    }
    let root = PathBuf::from(
        std::env::var("NEXUSDB_DEMO_OUTPUT")
            .map_err(|_| "--worker requires launcher environment")?,
    );
    let db = Arc::new(NexusDB::new()?);
    let start = std::time::Instant::now();
    let mut nodes = vec![
        json!({"id":1,"label":"Emergency","properties":{"synthetic":true}}),
        json!({"id":2,"label":"Ward","properties":{"synthetic":true}}),
        json!({"id":3,"label":"ICU","properties":{"synthetic":true}}),
        json!({"id":4,"label":"Transfer","properties":{"synthetic":true}}),
    ];
    let mut relationships = Vec::new();
    let intervals = [
        (1, 1, 2, 10, 20),
        (2, 2, 3, 5, 9),
        (3, 1, 4, 12, 20),
        (4, 4, 3, 14, 25),
        (5, 1, 3, 30, 40),
    ];
    for (id, a, b, from, to) in intervals {
        relationships.push(json!({"id":id,"node_a":a,"node_b":b,"rel_type":"TRANSFER","properties":{"valid_from":BASE+from*MINUTE,"valid_to":BASE+to*MINUTE,"duration_ms":0,"layer":"transfer","source":"synthetic-schedule"}}));
    }
    let mut state = seed;
    for i in 0..patients {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        let day = ((state >> 32) % 30) as i64;
        let patient = 10000 + i as u64;
        let document = 20000 + i as u64;
        nodes.push(json!({"id":patient,"label":"Patient","properties":{"synthetic":true,"name":format!("Synthetic-{i:05}"),"risk":(i%5)+1}}));
        nodes.push(json!({"id":document,"label":"Document","properties":{"synthetic":true,"text":format!("Simulated patient {i}: transfer to ICU"),"embedding":if i==0{vec![1.,0.,0.]}else{vec![0.,1.,0.]}}}));
        relationships.push(json!({"id":100+i as u64*2,"node_a":document,"node_b":patient,"rel_type":"DESCRIBES","properties":{"layer":"evidence","source":format!("synthetic-document-{i}")}}));
        relationships.push(json!({"id":101+i as u64*2,"node_a":patient,"node_b":3,"rel_type":"OCCUPIES","properties":{"valid_from":BASE+day*86400000,"valid_to":BASE+(day+1)*86400000,"layer":"care","source":"synthetic-admission"}}));
    }
    let input = json!({"nodes":nodes,"relationships":relationships});
    std::fs::write(
        root.join("simulated_hospital.json"),
        serde_json::to_vec_pretty(&input).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    db.garantir_banco_existente(DB).map_err(|e| e.message)?;
    db.configure_temporal_history(DB, true)?;
    db.install_snapshot(DB, &input)?;
    let initial = temporal_history::status(DB)?;
    let before = initial["stamp"]["recorded_at"]
        .as_i64()
        .ok_or("Missing history watermark")?;
    let mut checks = Vec::new();
    let mut outputs = serde_json::Map::new();
    let call = |name: &str, request: Value| -> Result<Value, String> {
        graph_routes::try_handle_graph_call(&db, DB, &format!("CALL {name}({request});"))
            .ok_or("Procedure not dispatched")?
    };
    let mut check = |name: &str, passed: bool| -> Result<(), String> {
        checks.push(json!({"name":name,"passed":passed}));
        if !passed {
            Err(format!("Validation failed: {name}"))
        } else {
            Ok(())
        }
    };
    let earliest = call(
        "graph.earliestArrival",
        json!({"source":1,"target":3,"departure":BASE,"projection":{"layers":["transfer"]}}),
    )?;
    let bfs = call(
        "graph.temporalBfs",
        json!({"source":1,"target":3,"departure":BASE,"projection":{"layers":["transfer"]}}),
    )?;
    check(
        "earliest arrival waits and selects chronological detour",
        earliest["resultados"][0]["path"]["nodes"] == json!([1, 4, 3])
            && earliest["resultados"][0]["path"]["arrival"] == BASE + 14 * MINUTE,
    )?;
    check(
        "temporal BFS minimizes hops",
        bfs["resultados"][0]["path"]["nodes"] == json!([1, 3])
            && bfs["resultados"][0]["path"]["arrival"] == BASE + 30 * MINUTE,
    )?;
    let impossible = call(
        "graph.earliestArrival",
        json!({"source":2,"target":3,"departure":BASE+10*MINUTE,"projection":{"layers":["transfer"]}}),
    )?;
    check(
        "reverse-time transfer is rejected",
        impossible["resultados"][0]["path"]["found"] == false,
    )?;
    let current_window = call(
        "graph.project",
        json!({"projection":{"temporal":{"kind":"window","start":BASE+10*MINUTE,"end":BASE+20*MINUTE,"mode":"any"},"layers":["transfer"]}}),
    )?;
    check(
        "window projection has expected transfer edges",
        current_window["total_relationships"] == 3,
    )?;
    let all_window = call(
        "graph.project",
        json!({"projection":{"temporal":{"kind":"window","start":BASE+10*MINUTE,"end":BASE+20*MINUTE,"mode":"all"},"layers":["transfer"]}}),
    )?;
    check(
        "continuous-coverage window excludes late arrivals",
        all_window["total_relationships"] == 1,
    )?;
    let rag_before = call(
        "graphRAG.temporalRetrieve",
        json!({"projection":{"system_at":before,"layers":["evidence","care"]},"vector":[1.,0.,0.],"seed_label":"Document","k":1,"depth":2}),
    )?;
    check(
        "historical vector retrieval selects expected document",
        rag_before["resultados"][0]["seeds"][0]["node_id"] == 20000,
    )?;
    check(
        "RAG exposes relationship evidence paths",
        rag_before["resultados"][0]["nodes"]
            .as_array()
            .unwrap()
            .iter()
            .any(|n| n["id"] == 10000 && n["evidence_path"] == json!([100])),
    )?;
    db.apply_replicated_node(DB,&json!({"id":10000,"label":"Patient","properties":{"synthetic":true,"name":"Synthetic-00000","risk":5}}))?;
    let corrected = temporal_history::status(DB)?["stamp"]["recorded_at"]
        .as_i64()
        .ok_or("Missing correction time")?;
    db.apply_replicated_relationship(DB,&json!({"id":2,"node_a":2,"node_b":3,"rel_type":"TRANSFER","properties":{"valid_from":BASE+11*MINUTE,"valid_to":BASE+20*MINUTE,"layer":"transfer","source":"retroactive-synthetic-correction"}}))?;
    let fixed = call(
        "graph.earliestArrival",
        json!({"source":1,"target":3,"departure":BASE,"projection":{"layers":["transfer"]}}),
    )?;
    check(
        "retroactive correction enables earlier path",
        fixed["resultados"][0]["path"]["nodes"] == json!([1, 2, 3])
            && fixed["resultados"][0]["path"]["arrival"] == BASE + 11 * MINUTE,
    )?;
    let old_path = call(
        "graph.earliestArrival",
        json!({"source":1,"target":3,"departure":BASE,"projection":{"system_at":before,"layers":["transfer"]}}),
    )?;
    check(
        "system-time query preserves pre-correction knowledge",
        old_path["resultados"][0]["path"]["nodes"] == json!([1, 4, 3]),
    )?;
    db.apply_replicated_delete_node(DB, &json!({"id":10000}))?;
    let ctx = ExecutionContext::new(
        Backend::Serial,
        Duration::from_secs(30),
        CancellationToken::default(),
    );
    let past = temporal_history::read(DB, Some(before), &ctx)?;
    let updated = temporal_history::read(DB, Some(corrected), &ctx)?;
    let latest = temporal_history::read(DB, None, &ctx)?;
    check(
        "deleted entities remain reconstructible",
        past.nodes[&10000].properties["risk"] == 1
            && updated.nodes[&10000].properties["risk"] == 5
            && !latest.nodes.contains_key(&10000),
    )?;
    let events = call(
        "graph.historyEvents",
        json!({"entity":"nodes","id":10000,"limit":100}),
    )?;
    check(
        "automatic journal records insert update delete",
        events["resultados"][0]["events"].as_array().unwrap().len() == 3
            && events["resultados"][0]["events"][2]["operation"] == "delete",
    )?;
    let cached = call(
        "graph.project",
        json!({"projection":{"system_at":before,"layers":["transfer"]}}),
    )?;
    let repeated = call(
        "graph.project",
        json!({"projection":{"system_at":before,"layers":["transfer"]}}),
    )?;
    check(
        "historical projection cache is reused",
        repeated["execution"]["cache"]["cache_hit"] == true && cached["total_relationships"] == 5,
    )?;
    let snapshot = nexusdb::storage::create_snapshot(DB)?;
    let archived =
        temporal_history::read_path(&snapshot.join("nexusdb.sqlite"), Some(before), &ctx)?;
    check(
        "full SQLite backup retains history",
        archived.nodes[&10000].properties["risk"] == 1,
    )?;
    let disk = call(
        "graph.diskBuild",
        json!({"snapshot_id":"before_correction","projection":{"system_at":before,"layers":["transfer"]}}),
    )?;
    let disk_bfs = call(
        "graph.diskBfs",
        json!({"snapshot_id":"before_correction","source":1,"max_depth":2,"max_nodes":10}),
    )?;
    check(
        "paged disk CSR traversal returns expected nodes",
        disk_bfs["resultados"][0]["resultados"]
            .as_array()
            .unwrap()
            .iter()
            .any(|n| n["node_id"] == 3),
    )?;
    db.storage_engines
        .lock()
        .map_err(|_| "Storage lock poisoned")?
        .get_mut(DB)
        .ok_or("Missing demo engine")?
        .load_on_startup()
        .map_err(|e| e.to_string())?;
    let reloaded = temporal_history::read(DB, Some(before), &ctx)?;
    check(
        "restart preserves deleted-entity history",
        reloaded.nodes.contains_key(&10000),
    )?;
    for (name, value) in [
        ("earliest_arrival", earliest),
        ("temporal_bfs", bfs),
        ("retroactive_path", fixed),
        ("historical_rag", rag_before),
        ("history_events", events),
        ("disk_snapshot", disk),
        ("disk_bfs", disk_bfs),
    ] {
        outputs.insert(name.into(), value);
    }
    let report = json!({"status":"passed","synthetic":true,"database":DB,"patients":patients,"nodes":input["nodes"].as_array().unwrap().len(),"relationships":input["relationships"].as_array().unwrap().len(),"seed":seed,"checks":checks,"outputs":outputs,"initial_history":initial,"elapsed_seconds":start.elapsed().as_secs_f64(),"hardware":{"os":std::env::consts::OS,"architecture":std::env::consts::ARCH,"logical_cpus":std::thread::available_parallelism().map_or(1,usize::from)},"scope":"functional validation; simulated embeddings; no GPU or NVMe throughput claim"});
    std::fs::write(
        root.join("report.json"),
        serde_json::to_vec_pretty(&report).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    println!(
        "PASS: {} checks; {} simulated patients",
        report["checks"].as_array().unwrap().len(),
        patients
    );
    Ok(())
}
