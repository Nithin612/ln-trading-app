//! engine-cli — native replay/bench entry for engine-core, no Python needed.
//!
//! Grows with the engine (replay in Phase 3, bench harness alongside
//! criterion). For now: version banner and a stdin indicator runner used
//! for quick manual checks:
//!
//!   echo "100 101.5 99.8 102.3 103.1" | engine-cli ema 5

use std::io::Read;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        None | Some("version") => {
            println!("engine-cli {}", engine_core::VERSION);
            ExitCode::SUCCESS
        }
        Some(cmd @ ("ema" | "rsi")) => run_indicator(cmd, args.get(1)),
        Some("backtest") => run_backtest_bench(args.get(1)),
        Some(other) => {
            eprintln!(
                "unknown command: {other} (try: version | ema N | rsi N | backtest <corpus.json>)"
            );
            ExitCode::FAILURE
        }
    }
}

fn run_backtest_bench(path: Option<&String>) -> ExitCode {
    use std::collections::BTreeMap;
    use std::time::Instant;

    let Some(path) = path else {
        eprintln!("usage: engine-cli backtest <corpus.json>");
        return ExitCode::FAILURE;
    };
    let Ok(raw) = std::fs::read_to_string(path) else {
        eprintln!("cannot read {path}");
        return ExitCode::FAILURE;
    };
    #[derive(serde::Deserialize)]
    struct Cols {
        open: Vec<f64>,
        high: Vec<f64>,
        low: Vec<f64>,
        close: Vec<f64>,
        volume: Vec<f64>,
    }
    let Ok(corpus): Result<BTreeMap<String, Cols>, _> = serde_json::from_str(&raw) else {
        eprintln!("bad corpus json");
        return ExitCode::FAILURE;
    };
    let stocks: Vec<(String, Vec<engine_core::types::Bar>)> = corpus
        .into_iter()
        .map(|(sym, c)| {
            let bars = c
                .open
                .iter()
                .zip(&c.high)
                .zip(&c.low)
                .zip(&c.close)
                .zip(&c.volume)
                .map(|((((&o, &h), &l), &cl), &v)| engine_core::types::Bar {
                    open: o,
                    high: h,
                    low: l,
                    close: cl,
                    volume: v,
                })
                .collect();
            (sym, bars)
        })
        .collect();

    let params = engine_core::backtest::BacktestParams {
        capital: match engine_core::risk::money_from_str("500000") {
            Some(v) => v,
            None => return ExitCode::FAILURE,
        },
        risk_pct: match engine_core::risk::money_from_str("2") {
            Some(v) => v,
            None => return ExitCode::FAILURE,
        },
        min_confidence: 70,
        weight_multipliers: Vec::new(),
    };

    // Warm run then timed run
    let t0 = Instant::now();
    let results = engine_core::backtest::run_universe(&stocks, "1d", &params);
    let elapsed = t0.elapsed();
    let trades: usize = results.iter().map(|(_, t)| t.len()).sum();
    println!(
        "stocks={} trades={} elapsed_ms={}",
        results.len(),
        trades,
        elapsed.as_millis()
    );
    ExitCode::SUCCESS
}

fn run_indicator(cmd: &str, length_arg: Option<&String>) -> ExitCode {
    let Some(length) = length_arg
        .and_then(|s| s.parse::<usize>().ok())
        .filter(|l| *l > 0)
    else {
        eprintln!("usage: engine-cli {cmd} <length>=1..  (values on stdin)");
        return ExitCode::FAILURE;
    };

    let mut input = String::new();
    if std::io::stdin().read_to_string(&mut input).is_err() {
        eprintln!("failed to read stdin");
        return ExitCode::FAILURE;
    }
    let values: Vec<f64> = input
        .split_whitespace()
        .filter_map(|t| t.parse::<f64>().ok())
        .collect();

    let out = match cmd {
        "ema" => engine_core::indicators::ema(&values, length),
        _ => engine_core::indicators::rsi(&values, length),
    };
    for v in out {
        println!("{v}");
    }
    ExitCode::SUCCESS
}
