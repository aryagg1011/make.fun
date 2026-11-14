from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forecast import forecast_market

PARAMS = {
    "step": 30,
    "price_band": 0.15,
    "half_life": 720.0,
    "empirical_blend": 0.80,
    "peer_blend": 0.50,
    "max_origins": 4,
}


def make_output(case: dict) -> dict:
    histories = [m["prices"] for m in case["markets"]]
    rows = []
    for market in case["markets"]:
        q = forecast_market(
            market["prices"], int(case["horizon_minutes"]),
            model="hybrid", peer_histories=histories, **PARAMS,
        )
        rows.append({"id": market["id"], "q": q})
    return {"forecasts": rows}


def main() -> None:
    input_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(input_dir.glob("*.in"), key=lambda p: p.name):
        case = json.loads(source.read_text(encoding="utf-8"))
        result = make_output(case)
        expected = {m["id"] for m in case["markets"]}
        got = {row["id"] for row in result["forecasts"]}
        if got != expected or len(result["forecasts"]) != len(expected):
            raise ValueError(f"market coverage mismatch in {source.name}")
        for row in result["forecasts"]:
            if len(row["q"]) != int(case["horizon_minutes"]):
                raise ValueError(f"horizon mismatch for {row['id']}")
            for values in row["q"]:
                if len(values) != 5 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                    raise ValueError(f"invalid quantile row for {row['id']}")
                if values != sorted(values):
                    raise ValueError(f"unordered quantiles for {row['id']}")
        target = output_dir / f"{case['case']}.out"
        target.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        if target.stat().st_size > 1_048_576:
            raise ValueError(f"output too large for {case['case']}")


if __name__ == "__main__":
    main()
