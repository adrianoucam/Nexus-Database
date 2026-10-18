//! Reproducible synthetic calibration; never opens or changes user databases.
//! NEXUSDB_CUDA_LIBRARY must point to the matching DLL for hardware measurements.
use nexusdb::{
    compute::{Backend, CancellationToken, ComputeRuntime, ExecutionContext},
    graph::GraphSnapshot,
    model::GraphRelationship,
};
use serde_json::json;
use std::time::Duration;

fn main() -> Result<(), String> {
    let threads = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1)
        .min(12);
    let runtime = ComputeRuntime::new(threads, 128 * 1024 * 1024, 1)?;
    let mut profiles = Vec::new();
    for n in [512usize, 10_000, 100_000] {
        let edges = (0..n)
            .flat_map(|a| (1..=10).map(move |step| (a, (a + step) % n)))
            .enumerate()
            .map(|(id, (a, b))| GraphRelationship {
                id: id as u64,
                node_a: a as u64,
                node_b: b as u64,
                rel_type: "E".into(),
                properties: serde_json::Value::Null,
            })
            .collect::<Vec<_>>();
        let graph = GraphSnapshot::build((0..n).map(|i| i as u64), &edges, None, 1)?;
        for pagerank in [false, true] {
            let ctx = ExecutionContext::new(
                Backend::Auto,
                Duration::from_secs(120),
                CancellationToken::default(),
            );
            let report =
                runtime.calibrate(&graph, pagerank, if pagerank { 20 } else { 1 }, 5, &ctx)?;
            profiles.push(json!({"vertices":n,"edges":edges.len(),"calibration":report}));
        }
    }
    println!("{}",serde_json::to_string_pretty(&json!({"threads":threads,"gpu":nexusdb::compute::cuda::identity().ok(),"topology":"directed ring with ten forward neighbors per vertex","profiles":profiles})).map_err(|e|e.to_string())?);
    Ok(())
}
