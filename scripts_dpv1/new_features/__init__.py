"""Rank 1-2 features built new for DPv1 (Phase 4B).

Each module exposes ``compute(raw, ctx, cfg, active) -> DataFrame`` at entry
grain, keyed on ``entry_id``, and emits only the columns named in ``active``.

``ctx`` carries the shared prior-race lookup (``ctx['prev']``) and career
counts (``ctx['career']``) so no module re-derives them.
"""
