# Model & Cost Strategy — LPU SmartNotice

## 1. Selected Gemini Models
- **Generation Model:** `gemini-3.1-flash-lite` (or `gemini-2.5-flash`). Fast, cost-efficient model with structured JSON output capabilities (`response_schema`).
- **Embedding Model:** `gemini-embedding-2` (or `text-embedding-004`). Supports custom output dimensions (`output_dimensionality=768`).

## 2. Cost Mitigation & Batch Safety Rules
Because the dataset contains 7,350 records, processing the entire dataset via LLM APIs could incur significant costs.

LPU SmartNotice implements multiple cost safeguards:
1. **Incremental Workflows:** Users must specify explicit safety limits (e.g. `--limit 25`).
2. **Full Dataset Safeguard:** Batch indexing requires explicit confirmation (`--confirm-full`).
3. **SQLite Caching:** Successful LLM extractions are cached in SQLite by content hash. Re-running the application costs 0 additional API credits.
4. **Local Fallback Heuristics:** If API keys are missing or unconfigured, the system automatically uses rule-based heuristic extraction without throwing runtime errors.

---
*Return to [Root README](../README.md)*
