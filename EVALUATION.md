# Frozen offline evaluation policy — version 1.0

Checkpoint 1. No model baseline has been measured. This policy and evaluation_cases.json are committed before baseline measurement. The initial source/plan commit is df3de423ac889a084b0cd7fd02a04f5d1c95dc29. No genuine Git repository was found in the starter or ancestors up to D:\. PLAN.md was created in the preceding planning turn before evaluator code existed; it has 255 words, approximately half a page. Its initial committed bytes are preserved. File timestamps alone are not the evidence of ordering; the session sequence and initial commit are.

## Run without credentials

From the starter root, using Python 3.10+:

```powershell
python evaluate.py score --predictions evidence/baseline
python -m unittest discover -p 'test_*.py' -v
```

`python evaluate.py` also works; it defaults to the above prediction directory. The evaluator never imports extract.py, executes extraction, or calls a provider. It uses Python's standard library only. Output is JSON on stdout; redirect it to a chosen file if required later. No baseline prediction files are created by tests or by the evaluator.

The saved-file contract is `<prediction-directory>/report_01.json` through the eight labelled report IDs: 01, 02, 03, 05, 06, 08, 09 and 11. Files contain the extractor's actual `{"tests": [...]}` output. The gold set has 138 rows. Do not copy gold files to manufacture a baseline. Test copies live only in automatically removed temporary directories and are explicitly synthetic.

An optional `run.json` documents attempted extractions. Format: `{"reports": {"report_01": {"status": "failed", "error": "timeout"}, "report_02": {"status": "success"}}}`. A recorded failure is authoritative even if a stale prediction file exists. A claimed success without its file is invalid. Unsupported manifest statuses and malformed manifests are evaluation errors, not omitted reports. Unlabelled predictions do not enter the headline score.

Exit codes: 0 = complete set of valid saved predictions; 1 = complete attempted set with invalid/failed extraction; 2 = unavailable outputs (including partial corpus); 3 = evaluation/configuration error. Code 0 means the offline inputs are valid, not that their extraction accuracy is high. If outputs do not exist, reports and aggregate metrics are null, status is unavailable, and the message says baseline outputs are required. A partial corpus has only an explicitly labelled observed-subset aggregate; full aggregate stays null. No missing file is silently interpreted as a measured empty extraction.

## Matching

- Match within a report, one-to-one. Normalize Unicode compatibility forms, whitespace and name case.
- First pair exact normalized names. Then pair remaining names using the explicit alias groups in evaluation_cases.json. Duplicate occurrences pair in source order. Values, units and reference ranges never influence pair selection.
- No fuzzy matching. No global removal of serum/urine, fasting/postprandial, direct/indirect, or total/free qualifiers. Bare RBC is not aliased to blood RBC Count. Albumin is not aliased to Serum Albumin. Unknown names remain unmatched.
- Aliases are predeclared from source vocabulary, not learned from predictions. Clinically uncertain mappings are deliberately excluded. Additions require a policy change and rescoring all saved versions.
- Record every match, missing gold row, unmatched prediction and field mismatch with one-based indices. Duplicate names are flagged even when valid repeated results. Order violations are a separate diagnostic.

## Field equality

- Name: exact normalized form or one of the frozen unambiguous aliases. Also report exact-name matches separately.
- Numeric values: Decimal equality. `13.50`, `13.5` and JSON number 13.5 agree. No rounding tolerance. Preserve sign and scale.
- JSON fractional numbers are read as Decimal so differing final digits do not collapse through float rounding. Decimal numbers in diagnostic source rows serialize as exact strings. Metric rates remain ordinary JSON numbers. ASCII JSON escapes keep pipe output portable on Windows; decoded content is unchanged.
- Only syntactically valid Western or Indian comma grouping is removed. `2,29,000` equals `229000`; malformed `2,29` does not equal `229`.
- Inequalities retain their exact comparator: `< 0.5` equals `<0.50`, but neither equals `0.5` or `<=0.5`. Unicode ≤/≥ are equivalent to <=/>=.
- Intervals retain both endpoints. `2–3` equals `2 - 3`, never `2`, `3` or `2.5`. Dash typography and surrounding whitespace are harmless.
- Qualitative values: Unicode/whitespace normalization and case folding only. `Negative`, `Nil`, `Present` and `Present (+)` remain distinct.
- Null matches null only. Empty string and the string `null` do not match null. Missing required keys make a prediction invalid.
- Units: case-sensitive after whitespace/Unicode normalization, with only explicit `g/dl -> g/dL` and `mg/dl -> mg/dL` aliases. µ and μ normalize equally. No conversion of lakh/cumm, /cumm, mmol/L or mg/dL; no generic case folding of SI units.
- Reference ranges use the same number/comparator/interval/text rules, including null. Never substitute standard ranges or derive physiological consistency.
- JSON must have the supplied schema's types and required fields. Additional properties are allowed, including baseline status. Reject malformed JSON, duplicate keys, booleans as values, and non-finite numbers. The validator implements this specific schema's shape, not a general JSON Schema engine. Empty names are permitted by the supplied schema but cannot match rows.

## Metrics

Let G = gold row count, P = predicted rows in a valid extraction, M = identity matches, C = matches correct in all four fields.

| Metric | Precision | Recall | F1 |
|---|---|---|---|
| Coverage (row identity only) | M/P | M/G | 2M/(P+G) |
| Complete row (primary) | C/P | C/G | 2C/(P+G) |

An identity-matched row with a wrong field counts as one complete-row false positive and one false negative. Unsupported rows specifically mean unmatched predictions (P−M). Missing rows mean G−M. Do not confuse incorrect values with unsupported row identities. Duplicate extras remain false positives; no deduplication.

Field accuracy is displayed over matched rows and over every expected row. Missing/failed rows are wrong in the latter denominator. Matched name accuracy includes aliases; exact-name counts expose naming drift. The qualitative/inequality/interval subset reports expected and correct counts, including omitted rows. Missing-range invention counts apply to matched rows with null gold ranges and non-null predictions. Read row mismatches and extra-row details alongside these diagnostics.

Per-report scores and micro sums over all eight reports are shown for both gold views. Macro complete-row F1 is the mean of the eight per-report F1s. Report 11 has 54 rows and must not hide smaller-report regressions. No confidence/generalization claims follow from this development set.

For nonempty gold and no predicted rows, precision is null (undefined), recall/F1 are 0. Valid empty extraction is scored, not classified as failed. Expected-empty documents have undefined precision/recall/F1 and a separate no-result pass/extra-row diagnostic. Recorded failure or invalid JSON gets zero correct rows, all expected rows missing, and a separate status; its rows get no credit. Failed expected-empty extraction never passes the no-result check. Unavailable files have no score at all.

## Imperfect labels

The known correction is report_01 row 14, Platelet Count: supplied value `304000`, source value `340000`. PDF text and visual review agree. The original gold files are never edited. The evaluator checks the original row identity/value before applying a deep-copied overlay; a changed source causes an evaluation error.

Publish original and adjudicated views side-by-side. The intended primary decision metric is adjudicated complete-row micro-F1, with original scores also visible. Corrections are evidence-backed and frozen before baseline. A later discrepancy or scorer bug requires documented policy revision and retrospective scoring of every saved variant. Do not adjust the metric to favor the final implementation.

## Checkpoint boundaries and limitations

Only the eight supplied gold reports are scored here. Four unlabelled reports need independent review references later; no manual gold has been invented in Checkpoint 1. Their IDs and deferred status appear in evaluation_cases.json and output.

Extraction latency, provider usage and cost are unavailable. Evaluator runtime is not extractor latency. Output includes fingerprints of evaluator, cases, supplied schema, gold, predictions and optional manifest so later comparisons can establish identical policies and inputs. Synthetic unit-test results are engineering evidence only, not model performance.

The source-faithfulness release objective is improved adjudicated complete-row micro-F1, no macro-F1 regression and no new confirmed unsupported results/invented ranges in the targeted reports. These gates are future checks, not scores obtained here. Model selection, API runs, usage instrumentation, extraction changes and unlabelled assessment belong to later checkpoints.

## Checkpoint 1 verification record

Executed `python -B -m unittest discover -p 'test_*.py' -v`: **38 tests passed, zero failed** on the final implementation. The first run had 30 passes and one CLI error caused by Windows pipe encoding; ASCII-safe JSON output fixed it. Added precision, manifest-validation and CLI-exit regressions. No tests execute extract.py or a provider.

Executed the saved-file evaluation with absent evidence/baseline: eight unavailable reports, zero valid/invalid/failed attempts, and null original/adjudicated aggregate scores, cost and extraction latency. This is an availability check, not baseline measurement. Protected-file SHA-256 hashes and Git diffs verify extractor, CLI source, schema, supplied reports/gold and committed planning documents are unchanged.
