"""Composable pipeline for validation, baseline evaluation and provenance manifests."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from arash.data.csv_loader import load_candles_csv
from arash.data.health import audit_csv_health
from arash.research.backtest import BacktestConfig, StrategyName, run_backtest
from arash.research.manifest import build_research_manifest

def run_research_pipeline(
    csv_path: str | Path, *, strategy: StrategyName = "buy-hold",
    config: BacktestConfig | None = None, generated_at: datetime | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    now=generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    health=audit_csv_health(csv_path,now=now)
    if health["status"] != "READY":
        return {
            "schema_version":1,"status":"BLOCKED_BY_DATA_QUALITY","data_health":health,
            "backtest":None,"manifest":None,
            "reason":"The input CSV is not READY; downstream evaluation was not run.",
            "trade_action":"NONE","execution_enabled":False,
        }
    candles=load_candles_csv(csv_path)
    result=run_backtest(candles,strategy=strategy,config=config)
    report={
        "schema_version":1,"status":"COMPLETED_OFFLINE_SIMULATION",
        "generated_at_utc":now.astimezone(timezone.utc).isoformat(),
        "data_health":health,"backtest":result.to_dict(include_trades=True),
        "source_path_name":Path(csv_path).name,
        "trade_action":"NONE","execution_enabled":False,"orders_submitted":False,
    }
    if output_path:
        import json
        path=Path(output_path);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True,default=str)+"\n",encoding="utf-8")
        report["output_path"]=str(path)
        manifest = build_research_manifest(path)
        manifest_path = path.with_suffix(path.suffix + ".manifest.json")
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["manifest"]=manifest
        report["manifest_path"]=str(manifest_path)
    else:
        report["manifest"]=None
    return report
