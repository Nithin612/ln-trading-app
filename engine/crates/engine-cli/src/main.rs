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
        Some(other) => {
            eprintln!("unknown command: {other} (try: version | ema N | rsi N)");
            ExitCode::FAILURE
        }
    }
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
