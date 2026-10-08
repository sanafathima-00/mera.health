# Checkpoint 2: unchanged-behavior Gemini 3.6 baseline

8 October 2026. Selected model: gemini-3.6-flash for this baseline and future comparisons, per explicit user decision. Extractor remains byte-identical to the starter. Seven new calls were made, one each for reports 02/03/05/06/08/09/11; report 01 was reused byte-for-byte from evidence/fallback_36_report01_20261008T114807Z, including its original latency and usage. No retry, billing enablement, or further model switch occurred. The earlier Gemini 3.8 failures and controlled recovery evidence remain separate.

## Execution and reproduction

Set GEMINI_API_KEY in the current process from ignored .env without printing it; extract.py does not load .env. Then select the approved model:

```powershell
$env:GEMINI_MODEL = 'gemini-3.6-flash'
python extract.py reports/report_02.pdf
python extract.py reports/report_03.pdf
python extract.py reports/report_05.pdf
python extract.py reports/report_06.pdf
python extract.py reports/report_08.jpg
python extract.py reports/report_09.jpg
python extract.py reports/report_11.pdf
```

These entry points were executed via runpy with the same sys.argv and model environment. Non-mutating urllib/json observers captured sanitized HTTP status, Date/Content-Type/Retry-After when present, response finish reasons/model version, and usageMetadata. Raw HTTP bodies and messages were not saved; classified error categories avoid report-content leakage. Observers returned successful responses unchanged and preserved failed response semantics. stdout/stderr are UTF-8 captures; successful predictions are byte copies of stdout, never repaired. Generic exception evidence records its class without sensitive details. TimeoutError is a transport failure, not a model extraction error.

Unchanged configuration: temperature 0, maxOutputTokens 16000, timeout 180 seconds, first PDF page at 60 DPI, one image, original prompt, no constrained JSON or thinking override. No automatic retry. Calls would stop on authentication/billing/quota errors; none occurred. Failed reports have manifest entries, not fabricated empty predictions.

Offline commands:

```powershell
python evaluate.py score --predictions evidence/baseline_36
python -B -m unittest discover -p 'test_*.py' -q
```

## All eight reports

P/R/F1 percentages below follow the frozen policy. A failed request has zero recall/F1 and undefined precision. Original complete-row precision and recall equal its F1 for both valid reports; all three are undefined/zero/zero for failures. Aggregate scores include request failures and are not a pure model-accuracy estimate.

| Report | Status | Matched/expected | Coverage P/R/F1 | Original complete F1 | Adjudicated complete P/R/F1 | Missing/unmatched | Attempt seconds |
|---|---|---:|---|---:|---|---:|---:|
| 01 | valid JSON | 14/14 | 100.00%/100.00%/100.00% | 92.86% | 100.00%/100.00%/100.00% | 0/0 | 11.392 |
| 02 | HTTP 503 | 0/16 | undefined/0.00%/0.00% | 0.00% | undefined/0.00%/0.00% | 16/0 | 10.862 |
| 03 | HTTP 503 | 0/8 | undefined/0.00%/0.00% | 0.00% | undefined/0.00%/0.00% | 8/0 | 41.830 |
| 05 | timeout | 0/14 | undefined/0.00%/0.00% | 0.00% | undefined/0.00%/0.00% | 14/0 | 181.067 |
| 06 | HTTP 503 | 0/12 | undefined/0.00%/0.00% | 0.00% | undefined/0.00%/0.00% | 12/0 | 42.927 |
| 08 | valid JSON | 1/6 | 16.67%/16.67%/16.67% | 16.67% | 16.67%/16.67%/16.67% | 5/5 | 7.021 |
| 09 | HTTP 503 | 0/14 | undefined/0.00%/0.00% | 0.00% | undefined/0.00%/0.00% | 14/0 | 9.774 |
| 11 | HTTP 503 | 0/54 | undefined/0.00%/0.00% | 0.00% | undefined/0.00%/0.00% | 54/0 | 93.989 |

Two predictions pass the frozen validator implementing the supplied schema shape/types. Six requests failed: five HTTP 503 responses and report 05 TimeoutError after approximately 181 seconds. There are zero malformed/invalid predictions and zero unavailable/unattempted reports. Frozen evaluator exit code 1 is expected for these recorded failures; metrics.json is unedited evaluator stdout.

## Field accuracy

Each cell is original correct / adjudicated correct / expected-row denominator. Exact-name diagnostics, matched-row denominators, every missing row, unmatched prediction and field mismatch are in metrics.json. Missing/request-failed rows count incorrect over expected rows.

| Report | Test name | Value | Unit | Reference range |
|---|---|---|---|---|
| 01 | 14/14/14 | 13/14/14 | 14/14/14 | 14/14/14 |
| 02 | 0/0/16 | 0/0/16 | 0/0/16 | 0/0/16 |
| 03 | 0/0/8 | 0/0/8 | 0/0/8 | 0/0/8 |
| 05 | 0/0/14 | 0/0/14 | 0/0/14 | 0/0/14 |
| 06 | 0/0/12 | 0/0/12 | 0/0/12 | 0/0/12 |
| 08 | 1/1/6 | 1/1/6 | 1/1/6 | 1/1/6 |
| 09 | 0/0/14 | 0/0/14 | 0/0/14 | 0/0/14 |
| 11 | 0/0/54 | 0/0/54 | 0/0/54 | 0/0/54 |

## Aggregate results

| Metric | Original | Adjudicated |
|---|---:|---:|
| Row coverage micro precision / recall / F1 | 75.00% / 10.87% / 18.99% | same |
| Complete-row micro precision / recall / F1 | 70.00% / 10.14% / 17.72% | 75.00% / 10.87% / 18.99% |
| Complete-row macro F1 | 13.69% | 14.58% |
| Complete rows / expected | 14 / 138 | 15 / 138 |
| Name, unit, range correctness over expected | 15 / 138 each | 15 / 138 each |
| Value correctness over expected | 14 / 138 | 15 / 138 |
| Value accuracy among 15 matched rows | 93.33% | 100% |
| Name, unit, range accuracy among matched rows | 100% each | 100% each |
| Missing / unmatched predicted rows | 123 / 5 | 123 / 5 |

## Confirmed failures and evaluation limitations

- Operational failures: reports 02, 03, 06, 09 and 11 returned HTTP 503; sanitized categories in their attempt records indicate overload/high demand where identifiable. Report 05 timed out without an HTTP response or usage metadata. Do not attribute these failures to row-reading behavior. No billing/quota/authentication error was observed.
- Report 08: the starter prompt requests standard names. Prediction row 4 says LDL Cholesterol, while the supplied label row 4 is LDL-C (Direct). The direct-method qualifier is lost. Other expanded names include Serum Cholesterol, HDL Cholesterol, VLDL Cholesterol and Cholesterol / HDL Ratio. The frozen alias policy does not match five of these rows; only TG -> Triglycerides matches. All six values, units and ranges agree by aligned manual comparison with supplied labels, but that is a diagnostic, not a revised headline score.
- Therefore five unmatched predictions do not establish five hallucinated laboratory results. Frozen name matching is restrictive and understates semantic recovery on report 08. Do not silently add aliases after seeing baseline predictions; any future approved policy revision must be versioned and applied to every saved variant.
- Report 01 platelet 340000 agrees with documented source/adjudication but differs from the unchanged supplied 304000 label. That sole value discrepancy accounts for the original/adjudicated difference.
- No predictions exist for report 11, so baseline evidence does not quantify page-two extraction omission. The first-page-only conversion remains a code-supported limitation, not an observed successful-output omission in this run.

## Latency, usage and cost

Baseline attempt time (including reused report 01): 398.863 seconds; mean 49.858 seconds/report. Seven new attempts: 387.471 seconds. Mean of the two successful attempts: 9.206 seconds. This is preparation plus request/parse or failure time, excluding observer setup/file persistence. Previous 3.8 attempts and recovery backoff are excluded. Report 01 occurred earlier; this is an aggregate of attempt times, not elapsed batch wall time.

| Report | Input tokens | Output tokens | Thinking tokens | Total tokens |
|---|---:|---:|---:|---:|
| 01 | 1242 | 886 | 1501 | 3629 |
| 02 | unavailable | unavailable | unavailable | unavailable |
| 03 | unavailable | unavailable | unavailable | unavailable |
| 05 | unavailable | unavailable | unavailable | unavailable |
| 06 | unavailable | unavailable | unavailable | unavailable |
| 08 | 1242 | 372 | 1020 | 2634 |
| 09 | unavailable | unavailable | unavailable | unavailable |
| 11 | unavailable | unavailable | unavailable | unavailable |

Observed totals for two successes: 2484 input, 1258 output, 2521 thinking, 6263 total. Failed-request usage and full-corpus usage are unavailable, not zero. JSON schema validity establishes shape only, not source fidelity.

Official standard prices verified 8 October 2026: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), $0.75/million input and $3.75/million output including thinking, through 31 December 2026. Formula: (input * 0.75 + (candidates + thoughts) * 3.75) / 1000000. Usage totals reconcile: input + output + thinking = total; no thinking double-count.

Paid list-price equivalent for the two observed successes: $0.01603425 total, $0.008017125 mean. Report 01: $0.00988275; report 08: $0.00615150. These are estimates, not charges. The project was confirmed free-tier by the user and the AI Studio UI showed Free tier during recovery investigation; no billing was enabled. Account invoice spend was not independently inspected. Full-corpus cost/report and a 10000-report/day projection remain unavailable because six usage records are absent and the two successes are not representative of the whole corpus. Production-volume free-tier quota is unverified.

## Verification and checkpoint boundary

38 tests passed, zero failed. All 26 protected starter/planning files are byte-identical to the initial commit; the evaluator, tests, cases and EVALUATION.md are unchanged. Original labels and the frozen platelet overlay remain untouched. Report 01 provenance and every previously committed baseline file are preserved. Secret scans cover evidence/documentation and the staged Git contents; .env remains ignored/untracked. Commit includes the controlled recovery/fallback history and new baseline evidence only, plus this document and a README summary.

The eight-report unchanged-behavior baseline is accounted for, including failures. Provider reliability and restrictive name matching limit improvement attribution. Later comparisons must retain gemini-3.6-flash and frozen scoring unless explicitly approved otherwise; do not interpret recovery from a 503 as an extraction-correctness improvement. No Checkpoint 3 work started.
