"""Batch offline execution sensitivity for a bounded list of paper order requests.

Each request is independently simulated against the same supplied candle series.
These runs do not represent aggregate shared-liquidity allocation between orders.
"""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Sequence
from arash.domain.models import Candle
from arash.paper.execution import ExecutionPolicy, simulate_execution

def simulate_execution_batch(
    candles:list[Candle], orders:Sequence[dict[str,Any]], *,
    policy:ExecutionPolicy|None=None, max_orders:int=100
)->dict[str,Any]:
    if type(max_orders) is not int or not 1<=max_orders<=1000:
        raise ValueError("max_orders must be an integer from 1 to 1000")
    batch=tuple(orders)
    if not batch: raise ValueError("orders must not be empty")
    if len(batch)>max_orders: raise ValueError(f"batch exceeds max_orders={max_orders}")
    base_policy=policy or ExecutionPolicy()
    seen:set[str]=set()
    results=[]
    for index,raw in enumerate(batch):
        if not isinstance(raw,dict): raise ValueError(f"order {index} must be an object")
        allowed={"client_order_id","side","quantity","submitted_at","order_type","limit_price"}
        unknown=set(raw)-allowed
        if unknown: raise ValueError(f"order {index} has unknown fields: {', '.join(sorted(unknown))}")
        client_id=str(raw.get("client_order_id","")).strip()
        if not client_id: raise ValueError(f"order {index} requires client_order_id")
        if client_id in seen: raise ValueError(f"duplicate client_order_id: {client_id}")
        seen.add(client_id)
        side=raw.get("side")
        if side not in ("buy","sell"): raise ValueError(f"order {client_id}: side must be buy or sell")
        try:
            quantity=raw["quantity"] if isinstance(raw["quantity"],Decimal) else Decimal(str(raw["quantity"]))
            submitted=raw["submitted_at"] if isinstance(raw["submitted_at"],datetime) else datetime.fromisoformat(str(raw["submitted_at"]).replace("Z","+00:00"))
            order_type=raw.get("order_type","market")
            limit_price=raw.get("limit_price")
            if limit_price is not None and not isinstance(limit_price,Decimal): limit_price=Decimal(str(limit_price))
        except (KeyError,ValueError,ArithmeticError) as exc:
            raise ValueError(f"order {client_id}: invalid quantity, timestamp or limit price") from exc
        if submitted.tzinfo is None or submitted.utcoffset() is None:
            raise ValueError(f"order {client_id}: submitted_at must be timezone-aware")
        if not quantity.is_finite() or quantity<=0: raise ValueError(f"order {client_id}: quantity must be finite and positive")
        result=simulate_execution(
            candles,side=side,quantity=quantity,submitted_at=submitted,
            order_type=order_type,limit_price=limit_price,policy=base_policy,
        )
        results.append({
            "client_order_id":client_id,
            "request_index":index,
            "request":{"side":side,"quantity":str(quantity),"submitted_at":submitted.astimezone(timezone.utc).isoformat(),
                       "order_type":order_type,"limit_price":str(limit_price) if limit_price is not None else None},
            "simulation":result.to_dict(),
        })
    payload={
        "schema_version":1,"report_type":"independent_batch_execution_simulation",
        "mode":"offline_paper_research_only","live_orders_submitted":False,
        "dataset_sha256":results[0]["simulation"]["dataset_sha256"],
        "request_count":len(results),"results":results,
        "limitations":[
            "Each request is evaluated independently against the same candle data.",
            "Volume capacity is not shared or reserved across batch requests, so sum of fills may exceed aggregate simulated venue capacity.",
            "Order ordering and queue priority are not represented.",
            "No account balances or positions are mutated and no live order is submitted.",
        ],
    }
    payload["report_fingerprint_sha256"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    return payload
