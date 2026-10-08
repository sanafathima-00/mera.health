# Lab report extraction: starter kit

Read the brief first. This file only covers what's in the kit and how to run it.

## Contents

- `extract.py`: the baseline extractor.
- `reports/`: 12 sample documents (`.pdf` and `.jpg`).
- `gold/`: labels for 8 of the 12, named after the report they belong to.
- `schema.json`: the output shape.

## Run it

Use Python 3.10 or newer and install Poppler, which provides `pdftoppm`:

- macOS: `brew install poppler`
- Ubuntu/Debian: `sudo apt-get install poppler-utils`

The supplied Gemini setup is one starting point. You can use free credits or adapt the starter to an accessible provider or a local open model; paid access is not required. If you change the model/provider to get started, measure the baseline with that setup before changing its extraction behavior, and document the substitution.

There are no Python package dependencies for the supplied setup. From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pdftoppm -v
python -c 'import getpass, os, subprocess, sys; env = os.environ.copy(); env["GEMINI_API_KEY"] = getpass.getpass("Gemini API key: "); sys.exit(subprocess.call([sys.executable, "extract.py", "reports/report_01.pdf"], env=env))'
```

The last command securely prompts for your key and runs one extraction as a setup smoke test. It makes an API call, which may incur charges depending on your account, and should print JSON containing a `tests` array. It does not save the key or put it in shell history. For repeated calls, set `GEMINI_API_KEY` through your usual local secret/environment setup; do not commit it.

The default model is `gemini-3.8-flash`. Google's [pricing page](https://ai.google.dev/gemini-api/docs/pricing) currently lists free-tier input and output for this model (checked 8 October 2026). You can start with a free-tier project and an API key from [Google AI Studio](https://aistudio.google.com/apikey). Check your project's [active rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): quotas apply per project, and access and limits may change. A key on a paid project can incur charges. If access or quota is insufficient, use another model or provider and document your setup.

The baseline calls the Gemini REST API. You're free to change model (`GEMINI_MODEL`) or provider; record the exact choice with your measurements. Whatever you change, this must keep working and keep printing schema-valid JSON to stdout, because it's how we'll run your version on reports you haven't seen:

```bash
python extract.py <path-to-report>
```

If your version needs different setup (other packages, other environment variables), say so at the top of your README.

For setup errors: a missing `pdftoppm` means Poppler is not on `PATH`; HTTP 401/403 means check key/project access, 404 means check model availability, and 429 means check quota. For a connection/TLS error, check network access before retrying. Never disable TLS verification. Keep access troubleshooting within the timebox; document constraints and any alternative you use.

## Checkpoint 1: offline evaluation

No successful accuracy baseline has been measured. Score real saved `report_<id>.json` predictions without credentials:

```powershell
python evaluate.py score --predictions evidence/baseline
python -m unittest discover -p 'test_*.py' -v
```

Missing outputs are **unavailable**, not measured failures or zero-score baselines. See [EVALUATION.md](EVALUATION.md) for frozen matching, normalization, failure accounting, metrics and manifest format. Original and adjudicated scores are both reported. [evaluation_cases.json](evaluation_cases.json) documents report 01's platelet correction (`304000` label versus `340000` source); supplied labels stay unchanged.

Decision log: kept direct source values and conservative aliases; rejected fuzzy name matching and unit-scale conversion. Verified the platelet discrepancy by PDF text and visual inspection. Preserved the 255-word plan before implementation in commit `df3de423ac889a084b0cd7fd02a04f5d1c95dc29`. The evaluator and synthetic tests do not execute the extractor or make model calls. Unlabelled-report review, provider measurement, and extraction improvements remain future work.

## Checkpoint 2: generation requests failed

After the user replaced the invalid key and confirmed free-tier eligibility, model metadata succeeded. All eight unchanged-extractor requests returned HTTP 503; no predictions or token usage were returned. [BASELINE.md](BASELINE.md), [run.json](evidence/baseline/run.json), and raw stdout/stderr record configuration and per-attempt latency (158.320 seconds total, 19.790 mean). [metrics.json](evidence/baseline/metrics.json) records eight failures: operational recall/F1 zero, precision undefined. These failures do not measure extraction accuracy. Original/adjudicated labels and evaluation policy are unchanged. 38 offline tests pass.

Decision log: kept the supplied model and requests unchanged; did not retry, silently substitute a model, or fabricate empty predictions. Only free-tier calls were authorized. Successful-report latency, token-based cost and 10000-report/day cost remain unavailable. .env is ignored; .env.example is a placeholder only. Do not assume production volume fits free-tier quota.

## Checkpoint 2: selected Gemini 3.6 baseline

For subsequent comparisons use `GEMINI_MODEL=gemini-3.6-flash` (explicit user decision); the extractor default/source is unchanged. [BASELINE_36.md](BASELINE_36.md) and [baseline_36 metrics](evidence/baseline_36/metrics.json) record all eight reports: report 01 reused with provenance, seven new single attempts, two valid outputs and six failures. Original/adjudicated complete-row micro-F1: 17.72%/18.99%; macro-F1: 13.69%/14.58%. Total attempt time 398.863 seconds; mean 49.858. Token usage exists only for two successes; full-corpus cost is unavailable.

Decision log: preserved the original model failures and two approved retries; selected 3.6 only after an approved single-report fallback. Kept frozen scoring despite report 08 name-matching limitations: five unmatched identities do not prove hallucination, and other fields agree with labels by manual comparison. Provider failures dominate this baseline; later accuracy attribution must account for them. 38 tests pass; protected files and policies are unchanged. No extraction improvements yet.

## Checkpoint 3: offline behavior fixes

[Actual prompts and rationale](PROMPTS.md). Removed numeric coercion and inferred status/ranges; preserve strings, finite numbers, units and nulls. Strict JSON/row validation and provider completion checks fail visibly instead of returning empty success. PDF conversion stays page 1 at 60 DPI. Use `GEMINI_MODEL=gemini-3.6-flash` for future comparisons; no generation calls were made in this checkpoint.

Verification: `python -B -m unittest discover -p 'test_*.py' -q` passes 64 tests (26 extractor, 38 evaluator), including mocked provider/CLI failures and saved baseline fixtures. Protected labels/reports/plan/schema and frozen evaluator remain unchanged. Saved baseline rescoring is identical. These are offline correctness fixes, not a measured extraction-accuracy improvement; live evaluation and all-page support remain pending.

## Checkpoint 4: all PDF pages

PDFs now render every page at 60 DPI, sort numerically, and send all page images in one complete-document request. JPG/PNG bytes, CLI and schema remain compatible. Rendering failure, timeout, missing/empty page output fails before generation; temporary files are cleaned up. No OCR branch, per-page calls, page cap or resolution change. [Compatibility and actual request prompt](PROMPTS.md#checkpoint-4-complete-document-image-request).

Offline verification: 74 tests passed, zero failed/skipped. Real Poppler plus mocked requests confirms report 01 sends one PNG and report 11 sends both PNGs in one call. Synthetic ordering checks pages 1 through 10. Original assets, plan, evaluator and historical evidence are unchanged; baseline rescoring is identical. Live accuracy, latency/cost and large-document limits remain unmeasured. No generation calls or Checkpoint 5 work occurred.
