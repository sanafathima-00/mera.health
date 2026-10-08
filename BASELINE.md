# Checkpoint 2: generation failed, accuracy baseline unavailable

Checked 8 October 2026. Source revision: `c2e319f0c4c3b630faa5ee4a088251e5ae0a3a81`.

## Environment and access

Python 3.10.9 and Poppler 26.07.0 are available. No dependencies installed. The original key failed metadata authentication with API_KEY_INVALID. After the user replaced the key in ignored .env and confirmed free-tier eligibility, model metadata returned HTTP 200 for gemini-3.8-flash and listed generateContent support. Billing eligibility is user-confirmed, not independently audited. Only free-tier calls were authorized; no paid project was selected.

Google documents image input and structured output support: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash . The starter does not request constrained JSON. Gemini 3.6 Flash is a documented alternative; it was not substituted or tested.

## Actual execution and measurement

Executed all eight unchanged CLI entry points, once each, via runpy with sys.argv set to the commands below. A json.load observer collected usageMetadata when present, returned the original response object unchanged, and was restored after each attempt. The extractor source and outgoing request configuration were unchanged. stdout/stderr were captured in memory and saved as UTF-8 text; no outputs were edited. SystemExit became the recorded exit code. Wall time used time.perf_counter around the complete CLI run, including rendering. No automatic retries or model substitutions occurred.

```powershell
python extract.py reports/report_01.pdf
python extract.py reports/report_02.pdf
python extract.py reports/report_03.pdf
python extract.py reports/report_05.pdf
python extract.py reports/report_06.pdf
python extract.py reports/report_08.jpg
python extract.py reports/report_09.jpg
python extract.py reports/report_11.pdf
python evaluate.py score --predictions evidence/baseline
python -B -m unittest discover -p 'test_*.py' -q
```

Configuration: model gemini-3.8-flash, temperature 0, maxOutputTokens 16000, timeout 180 seconds, PDF first page only at 60 DPI, original prompt, no response MIME/schema or explicit thinking configuration. CLI commands alone do not capture provider usage; the observer described above was used for measurement. Its execution is recorded in the agent transcript.

## Per-report evidence

| Report | Result | Expected rows missing | Attempt seconds |
|---|---|---:|---:|
| 01 | HTTP 503 | 14 | 15.974 |
| 02 | HTTP 503 | 16 | 4.050 |
| 03 | HTTP 503 | 8 | 48.124 |
| 05 | HTTP 503 | 14 | 11.077 |
| 06 | HTTP 503 | 12 | 29.809 |
| 08 | HTTP 503 | 6 | 4.663 |
| 09 | HTTP 503 | 14 | 5.532 |
| 11 | HTTP 503 | 54 | 39.092 |

Every attempt exited 1 with the starter's Gemini HTTP 503 error. The provider's underlying cause is unknown; 503 alone does not establish quota exhaustion or bad extraction behavior. No successful predictions exist. Empty stdout files are raw failure evidence, not empty valid JSON extractions. run.json makes all eight failures explicit. No output was substituted with an empty tests array.

## Frozen evaluation results

Saved metrics.json is the evaluator's unedited stdout. Exit code 1: all attempts accounted for, 8 failed, 0 valid, 0 invalid, 0 unavailable. Both original and adjudicated label views have identical operational results:

| Metric | Result |
|---|---:|
| Coverage precision | Undefined (null) |
| Coverage recall / F1 | 0 / 0 |
| Complete-row micro precision | Undefined (null) |
| Complete-row micro recall / F1 | 0 / 0 |
| Macro complete-row F1 | 0 |
| Four field accuracies over expected rows | 0 / 138 each |
| Four field accuracies among matched rows | Undefined (null) |
| Missing rows | 138 |
| Unsupported predicted rows | 0 |

These are failure-inclusive operational scores, not measured model extraction accuracy. No returned rows exist to assess hallucination, value/unit/range accuracy, or schema validity. Per-report recall/F1 and expected-row field accuracy are zero; precision and matched-row field accuracy are undefined. Report 01's supplied platelet label 304000 versus document/adjudicated 340000 remains explicitly overlaid; original files are untouched.

The earlier eight-unavailable preflight evaluation is retained as evidence/preflight_metrics.json. It is historical evidence and must not be confused with the failed-attempt results.

## Latency and cost

Total measured attempt time: 158.320 seconds. Mean failed-attempt time: 19.790 seconds. Successful-report latency is unavailable. Per-report durations are in run.json and the table above. Provider token usage is unavailable for every attempt; no generation response reached the usage observer.

Official published standard pricing checked 8 October 2026: USD $0.75 per million input tokens and $3.75 per million output tokens including thinking, through 31 December 2026: https://ai.google.dev/gemini-api/docs/pricing . A free tier is documented. Free-tier requests have zero listed price, conditional on confirmed eligibility; no invoice/account spend was inspected.

Paid list-price equivalent/report = (input_tokens * 0.75 + billed_output_including_thinking_tokens * 3.75) / 1000000. Do not double-count thinking. Token-based cost/report and its 10000-report/day projection are unavailable because no usage was returned. Free-tier eligibility for eight reports does not establish sufficient quota for 10000/day. No daily throughput or successful-report cost can be inferred from these failed requests.

## Verification and stopping boundary

38 offline tests passed; zero failed. All 26 protected starter/planning files match the initial commit byte-for-byte, including extractor, schema, PLAN, reports and gold. Frozen evaluator, cases, tests and EVALUATION.md match Checkpoint 1. .env is ignored and untracked; .env.example contains only the placeholder. Evidence and staged files are checked for the actual credential and credential signatures before committing.

This checkpoint records a reproducible failure attempt, not a usable accuracy baseline. A deliberate later retry or an explicitly approved model substitution is needed before comparing extraction improvements. Preserve this run and record future attempts separately. No extraction improvements began.
