# Localization progress — 2026-10-18

The clean capture observed 167,859 .data sources identical to both N10 baselines, with stable counters and no capture failures. This establishes the observed route/build, not all game text.

Residual locres uses fresh clean/runtime observations. Every .data source and captured substitution is excluded regardless of translation state. Legacy NDJSON contributes literal-source translation reuse only; historical IDs are not added. FormatString is reconciled independently with current templates.

| Route | Entries | Translated | Other decisions |
|---|---:|---:|---|
| Native .data | 167,859 | 160,460 | 4,570 missing; 2,829 ignore |
| Residual locres | 36,809 | 36,681 | 114 missing; 14 ignore |
| FormatString | 28,238 | 27,685 | 489 ignore; 64 missing |

| Per-source quality (EN enum) | Distinct sources |
|---|---:|---:|
| ignore | 3,082 |
| source_reviewed | 36,602 |
| unreviewed | 151,423 |
| untranslated | 4,685 |

Missing workload: 4,685 sources / 65,701 total source characters, including internal/technical candidates. This is not a visible-UI count.

The unattended workflow has independently reviewed 41,125 unique missing inputs: 36,153 new translations and 290 deliberate source retains imported; 4,682 inputs remain unresolved. Corrections use new attempts and independent review, not duplicated source-input credit. Another 145 whole-source legacy matches were reused and remain unreviewed.

Quality evidence binds source and target SHA. Structural QA and game startup do not certify meaning or client behavior. See [quality](quality-vi.json), [checkpoint](current-progress.json) and [throughput](throughput.json).

The initial41,125missing-source first pass is complete;4,685context/consumer/repair holds remain. Legacy pilot260pairs produced204approved,40needs_repair and16needs_context. First legacy review provisionally18–30processinghours from actual band timings; full repair and context completion are not yet estimated.

Installed runtime revision `local-reviewed-20261018-41125` has 160,460 native translations and 36,681 locres entries. Actual installed revision is `local-reviewed-20261018-41125`; current prepared revision installation is complete. All 27 full-Vietnamese font/widget/line-breaking base assets are preserved. All 138 Python tests and normal/far fixtures for both native profiles passed; PAK payloads and locres source hashes/targets were read back. Hosted CI has not run; gameplay testing remains pending.

Unresolved missing holds remain explicit; existing translations now enter independent review and fresh per-pair repair through immutable batches and coordinator-only imports. A quiet 10-minute continuation is active. No unattended game launch/login or publishing is authorized.
