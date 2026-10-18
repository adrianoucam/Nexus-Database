//! Isolated benchmark; launched by examples/agent-tools/benchmark.py.
use nexusdb::{
    agent::{
        executor::ToolExecutor,
        registry,
        tool::{ToolBudget, ToolRequest},
    },
    model::NexusDB,
};
use serde_json::json;
use std::{sync::Arc, time::Instant};
fn main() -> Result<(), String> {
    if std::env::var("NEXUSDB_AGENT_BENCH").as_deref() != Ok("isolated") {
        return Err("Use examples/agent-tools/benchmark.py to isolate benchmark data".into());
    }
    let mode = std::env::args().nth(1).unwrap_or_default();
    if mode != "native" && mode != "agent" {
        return Err("mode must be native or agent".into());
    }
    let db = Arc::new(NexusDB::new()?);
    db.garantir_banco_existente("bench")
        .map_err(|e| e.message)?;
    {
        let mut engines = db.storage_engines.lock().map_err(|_| "storage lock")?;
        let engine = engines.get_mut("bench").ok_or("bench absent")?;
        for i in 0..1000 {
            engine.insert_node("Item", &json!({"group":i%10,"value":i}));
        }
    }
    let registry = registry::shared().map_err(|e| e.message)?;
    let executor = ToolExecutor::default();
    let mut samples = Vec::new();
    let mut size = 0;
    let mut serialize_ms = Vec::new();
    for round in 0..35 {
        let start = Instant::now();
        let result = if mode == "native" {
            nexusdb::relationship_optimizer::db_stats(&db, "bench")?
        } else {
            executor
                .execute(
                    registry,
                    db.clone(),
                    "admin",
                    "database.stats",
                    ToolRequest {
                        database: "bench".into(),
                        input: json!({}),
                        budget: ToolBudget::default(),
                    },
                )
                .map_err(|e| e.message)?
                .result
        };
        let ms = start.elapsed().as_secs_f64() * 1000.0;
        let start = Instant::now();
        size = serde_json::to_vec(&result)
            .map_err(|e| e.to_string())?
            .len();
        let serialization = start.elapsed().as_secs_f64() * 1000.0;
        if round >= 5 {
            samples.push(ms);
            serialize_ms.push(serialization);
        }
    }
    samples.sort_by(f64::total_cmp);
    serialize_ms.sort_by(f64::total_cmp);
    println!(
        "BENCH:{}",
        json!({"mode":mode,"nodes":1000,"samples":samples.len(),"p50_ms":samples[15],"p95_ms":samples[28],"serialization_p50_ms":serialize_ms[15],"result_bytes":size,"samples_ms":samples})
    );
    Ok(())
}
