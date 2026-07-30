"""Longshot detection + per-race JSON output for the v2a ITM model.

A **longshot flag** fires on an entry when ALL three of:

    1. model P(ITM) > 0.25   — model thinks the horse has a real chance
    2. market P(ITM) < 0.20  — tote board is bearish (odds too long)
    3. rank outside top 3 by model P(ITM)  — not already a "contender"

Field-size-adaptive contender pick:
    * Field size <= 6: report top 3 contenders
    * Field size >= 7: report top 4 contenders

The result is a per-race dictionary suitable for pretty JSON dumps, with
horses ranked by P(ITM), longshot flags attached, and race context.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_LONGSHOT_MODEL_MIN = 0.25
DEFAULT_LONGSHOT_MARKET_MAX = 0.20
DEFAULT_LONGSHOT_MIN_RANK = 4     # rank >= 4 means outside top 3


@dataclass(frozen=True)
class LongshotConfig:
    model_p_min: float = DEFAULT_LONGSHOT_MODEL_MIN
    market_p_max: float = DEFAULT_LONGSHOT_MARKET_MAX
    min_rank: int = DEFAULT_LONGSHOT_MIN_RANK


def flag_longshots(
    p_model_itm: np.ndarray,
    p_market_itm: np.ndarray,
    ranks: np.ndarray,
    config: LongshotConfig | None = None,
) -> np.ndarray:
    """Boolean array — True where the entry is a longshot include."""
    cfg = config or LongshotConfig()
    p_model = np.asarray(p_model_itm, dtype=float)
    p_market = np.asarray(p_market_itm, dtype=float)
    ranks = np.asarray(ranks, dtype=int)
    return (
        (p_model > cfg.model_p_min)
        & (p_market < cfg.market_p_max)
        & (ranks >= cfg.min_rank)
    )


# ---------------------------------------------------------------------------
# Per-race output builder
# ---------------------------------------------------------------------------

def _contender_count(field_size: int) -> int:
    return 3 if field_size <= 6 else 4


def _confidence(p_model_itm_top: float, field_size: int) -> str:
    """Simple confidence signal based on how bullish the top pick is.

    ``top_p`` is P(ITM) of the model's #1 pick. In a random race with
    field size N, expected top P(ITM) ≈ 3/N; larger means the model has
    concentrated its belief. Buckets tuned informally.
    """
    baseline = 3.0 / max(field_size, 3)
    ratio = p_model_itm_top / baseline if baseline > 0 else 0.0
    if ratio >= 2.0:
        return "high"
    if ratio >= 1.5:
        return "medium"
    return "low"


def build_race_output(
    race_row: dict[str, Any],
    entries: pd.DataFrame,
    config: LongshotConfig | None = None,
) -> dict[str, Any]:
    """Return a structured dict for one race.

    ``race_row`` should contain race_id, race_date, race_num, track,
    surface, distance_yards, field_size, race_type.

    ``entries`` should have columns:
        entry_id, horse_name, program_num, post_pos, final_odds,
        p_model_itm, p_market_itm, finish_pos (optional)
    """
    field_size = int(race_row["field_size"])
    cfg = config or LongshotConfig()
    e = entries.copy().reset_index(drop=True)
    e = e.sort_values("p_model_itm", ascending=False).reset_index(drop=True)
    e["rank"] = np.arange(1, len(e) + 1)
    flags = flag_longshots(
        e["p_model_itm"].to_numpy(),
        e["p_market_itm"].to_numpy(),
        e["rank"].to_numpy(),
        config=cfg,
    )
    e["longshot_flag"] = flags
    n_contenders = _contender_count(field_size)

    horses_out = []
    for _, row in e.iterrows():
        horses_out.append({
            "rank": int(row["rank"]),
            "horse_name": row.get("horse_name"),
            "program_num": row.get("program_num"),
            "post_pos": int(row["post_pos"]) if pd.notna(row.get("post_pos")) else None,
            "final_odds": float(row["final_odds"]) if pd.notna(row.get("final_odds")) else None,
            "p_model_itm": round(float(row["p_model_itm"]), 4),
            "p_market_itm": round(float(row["p_market_itm"]), 4),
            "edge_vs_market": round(float(row["p_model_itm"] - row["p_market_itm"]), 4),
            "is_contender": bool(row["rank"] <= n_contenders),
            "longshot_flag": bool(row["longshot_flag"]),
            "finish_pos": int(row["finish_pos"]) if pd.notna(row.get("finish_pos")) else None,
        })

    top_p = float(e["p_model_itm"].iloc[0]) if len(e) else 0.0
    return {
        "race_id": int(race_row["race_id"]),
        "race_date": str(race_row.get("race_date")),
        "race_num": int(race_row.get("race_num")) if pd.notna(race_row.get("race_num")) else None,
        "track": race_row.get("track_code"),
        "surface": race_row.get("surface"),
        "distance_yards": (int(race_row["distance_yards"])
                            if pd.notna(race_row.get("distance_yards"))
                            else None),
        "race_type": race_row.get("race_type"),
        "field_size": field_size,
        "n_contenders": n_contenders,
        "confidence": _confidence(top_p, field_size),
        "longshot_count": int(flags.sum()),
        "horses": horses_out,
    }


def build_dataset_output(
    races_meta: pd.DataFrame,
    predictions: pd.DataFrame,
    config: LongshotConfig | None = None,
) -> list[dict[str, Any]]:
    """Convert a table of predictions across many races into a list of dicts.

    ``races_meta`` — one row per race with the context columns.
    ``predictions`` — one row per entry with prediction columns.
    """
    grouped = predictions.groupby("race_id")
    out: list[dict[str, Any]] = []
    for race_id, ent in grouped:
        row = races_meta.loc[races_meta["race_id"] == race_id]
        if row.empty:
            continue
        out.append(build_race_output(row.iloc[0].to_dict(), ent, config=config))
    return out


# ---------------------------------------------------------------------------
# CLI: pretty-print one race for spot checks
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo_race = {
        "race_id": 999, "race_date": "2026-05-01", "race_num": 5,
        "track_code": "GP", "surface": "Turf", "distance_yards": 1760,
        "race_type": "ALLOWANCE", "field_size": 8,
    }
    entries = pd.DataFrame({
        "entry_id":   [1, 2, 3, 4, 5, 6, 7, 8],
        "horse_name": ["Fav", "Second", "Contender", "Chalky4",
                        "Sleeper", "Bomb", "Nope", "AlsoNope"],
        "program_num": [str(i) for i in range(1, 9)],
        "post_pos":   list(range(1, 9)),
        "final_odds": [1.2, 2.5, 3.5, 6.0, 12.0, 25.0, 30.0, 40.0],
        "p_model_itm": [0.75, 0.55, 0.50, 0.35, 0.30, 0.20, 0.15, 0.10],
        "p_market_itm":[0.80, 0.65, 0.50, 0.35, 0.18, 0.12, 0.10, 0.07],
        "finish_pos": [1, 2, 4, 6, 3, 5, 7, 8],
    })
    print(json.dumps(build_race_output(demo_race, entries), indent=2))
