# Lab-report extractor: requirements and implementation plan

Status: Checkpoint 0 proposal for review. Created 8 October 2026. No implementation, dependency installation, test execution, model calls, Git initialization, or commits are authorized by this document alone.

## 1. Objective and evidence boundary

Improve the supplied extractor's faithful recovery of document-supported laboratory results. Demonstrate the change with a fixed evaluation, report/row evidence, latency, and cost. Preserve the CLI. Complete within approximately 4–6 hours of total engineering work, including analysis and planning already spent.

This is a prototype assessment, not a clinical product. Completeness is an objective, not a guarantee that a model can read every ambiguous document. Local validation guarantees output shape, not source truth. Human-reviewed evidence must establish accuracy improvements.

The brief, README, schema, complete extractor, all eight gold files, and all twelve documents have been inspected. Text-bearing PDF contents and image-only PDFs/photos were inspected with read-only tools. No extraction run or score exists yet. Provider access and prices remain unverified. The checkout currently has no Git repository.

### Confirmed starter facts

| Evidence | Finding | Source |
|---|---|---|
| PDF conversion command | Only page one at 60 DPI is sent | extract.py:19–20, 40–52 |
| Report 11 | Two pages; 30 rows on page one and 24 on page two | reports/report_11.pdf; gold/report_11.json |
| Numeric coercion | Text, intervals, inequalities and comma-formatted strings cannot survive faithfully | extract.py:29–33, 89–106; gold/report_06.json and report_09.json |
| Missing ranges | Prompt explicitly instructs invention | extract.py:32; report_03 T3, T4 and Glycated Hb |
| Parsing | Exceptions silently become an empty result | extract.py:81–86 |
| Validation | schema.json is not loaded; provider response completion is not checked | extract.py:55–111 |
| Gold discrepancy | Report 01 platelet count is 340000; supplied label is 304000 | reports/report_01.pdf; gold/report_01.json:81–85 |
| Negative document | Report 12 is a prescription with vitals, medication doses and advised investigations, without lab results | reports/report_12.jpg |
| Evaluation | 138 supplied rows; no evaluator, tests or saved predictions | gold/; repository inventory |

## 2. Assessment requirements versus proposed behavior

### Explicit assessment requirements

| ID | Requirement | Source |
|---|---|---|
| A1 | Commit a roughly half-page initial PLAN.md before writing code; do not rewrite it afterward | brief.md:20 |
| A2 | Define correctness, build a one-command evaluation, score baseline, assess four unlabelled reports | brief.md:21, 72 |
| A3 | Identify three important failure categories with report/row root causes | brief.md:22 |
| A4 | Improve extraction; compare before/after, latency and cost/report | brief.md:23 |
| A5 | Report an attempted change that did not help, with numbers | brief.md:24 |
| A6 | Give one problem-specific paragraph each on RAG, fine-tuning and a multi-step agent | brief.md:25–28 |
| A7 | Keep python extract.py <file> printing schema-valid JSON; six unseen reports will be used | brief.md:30 |
| A8 | Preserve meaningful unsquashed Git history and README decision log | brief.md:39–40 |
| A9 | Submit code/history, original plan, README no longer than two pages, eval/output, prompts and rationale | brief.md:67–74 |
| A10 | Stay within 4–6 hours and submit within five days of receipt | brief.md:46 |
| A11 | Any accessible provider/model allowed; report cost even with zero spend; exclude secrets | brief.md:50 |
| A12 | If provider/model substitution is needed, baseline that setup before extraction changes | README.md:19 |

Transcripts are strongly encouraged and optional; include unedited sessions if chosen (brief.md:38). Process and outcome carry roughly equal weight. Evidence, verification, model/cost choices, and decisions not to build are assessed (brief.md:52–65).

### Proposed functional contract for approval

| ID | Proposed requirement | Acceptance |
|---|---|---|
| F1 | Accept .pdf, .jpg, .jpeg and .png, case-insensitively | Successful mocked CLI/input coverage; unknown suffix gets a clear failure |
| F2 | Render every PDF page; numeric page order | Report 11 includes page-two input; page numbering does not sort 10 before 2 |
| F3 | Extract each visible laboratory result row, including qualitative results | Review omissions and extras per report; no hardcoded report-specific values |
| F4 | Preserve printed names and result meaning | Strings remain strings; <, >, ranges, + and grouped digits are not dropped |
| F5 | Preserve source units and reference ranges | Associate unit with its row even if printed beside a value or within a range; do not convert scale |
| F6 | Missing/illegible value, unit or range becomes null | Visible test name with unreadable value remains a row with null; unknown names are not invented |
| F7 | Exclude medications, vitals, requested tests without results, recommendations and headings | Report 12 returns {"tests": []}; report 07 handwriting is not a result |
| F8 | Success emits only schema-valid result JSON to stdout | Four required keys; finite numbers only; no logs on stdout |
| F9 | Provider/conversion/parse/validation failures are visible | Nonzero exit, concise stderr, no success JSON and no partial document output |
| F10 | Keep existing invocation and schema unchanged | python extract.py <file>; no required new CLI argument |

F2–F9 are explicit objectives from the user's planning request and proposed resolutions of gaps in the starter. They are not additional requirements quoted from the CTO brief. F3 does not imply a guaranteed perfect extraction score.

### Non-functional requirements and scope

- Keep Python standard-library implementation and Poppler. Reuse the supplied REST integration; no framework or generalized provider abstraction.
- Support Windows/PowerShell setup in final documentation; retain normal Python portability.
- Bound conversion and HTTP waits. Initial proposal: conversion timeout 60 seconds, HTTP timeout 180 seconds. Evaluation subprocess timeout 300 seconds. Validate these bounds with actual runs later; timeout adjustments must be logged.
- No automatic retries initially. Fail and record the cause. An explicit rerun is a separate attempt with its cost/latency retained; do not retry authentication failures blindly.
- Do not print secrets, request headers, credential values, or raw private environment dumps. Keep TLS verification enabled.
- One successful document request by default. Measure total preparation, network, parsing and validation time.
- Preserve original brief, reports, gold and schema. Only update README/extractor after later approval. PLAN.md becomes immutable once committed.
- Excluded: UI, database, queue, deployment, service layer, training, RAG, agents, broad OCR routing, clinical interpretation, speculative normalization and patient metadata extraction.
- Avoid report-ID/template-specific extraction rules. Small documented evaluator aliases are distinct from extraction rules.

## 3. Minimal recommended architecture

### Data flow

CLI path -> input checks -> ordered page images -> one vision request -> strict JSON parsing -> schema/type/semantic checks -> result JSON.

Evaluation is separate: saved outputs + original labels + reviewed overlay -> fixed matching/scoring -> metrics/errors/timing/cost evidence.

### Components in extract.py

1. **Input preparation:** validate file and suffix. Images keep their original bytes. PDFs render all pages using pdftoppm into a TemporaryDirectory. Sort generated page numbers numerically. Encode every page; add page boundaries to request instructions. Do not cap pages silently. If conversion/provider limits prevent processing the complete document, fail explicitly.
2. **Vision request:** a single ordered image list and one source-faithful prompt. Start from the existing model configuration. Keep temperature 0 and record output-token limit. Ask for exactly the four schema fields; do not generate computed status. Remove the numerical-only and standard-range rules. Instruct left-table top-to-bottom then right-table top-to-bottom within a shared section, sections and pages in document order. Do not infer physiological relationships or correct implausible source values.
3. **Generation format:** request JSON and schema-constrained generation only after confirming support for the selected model. Use a compatible provider-schema subset representing the unchanged schema. A rejected configuration is a visible setup failure, not a silent second request.
4. **Response handling:** check candidates, safety/block state and finish reason using the provider's actual documented response contract. Empty, blocked or truncated output fails. Keep raw response and usage in evaluation evidence, without headers/secrets.
5. **Parsing:** parse exactly one JSON object. For an unconstrained provider, allow at most one enclosing Markdown code fence; no greedy regex extraction, substring guessing or LLM repair.
6. **Local validation:** enforce the current schema's required object/array/field types using a small explicit standard-library validator; reject booleans as numeric values, non-finite numbers, non-object rows, and absent required keys. Enforce non-empty printed names as an additional application rule. Accept extra properties as the supplied schema does, but generate only four fields. Validate schema subset against documented schema fixtures; do not claim a generic JSON Schema engine.
7. **Lossless cleanup:** trim boundary whitespace only. Preserve values as returned strings or finite numbers; encourage strings in the prompt to retain source formatting. Do not float-coerce, convert units, deduplicate rows, fabricate missing fields, assign statuses or impose medical ranges. JSON null, not the string "null", represents missing information.
8. **CLI errors/measurement:** return a complete valid document or fail. A successful non-lab document may legitimately return an empty array. Parse/provider failures never become an empty success. Print JSON with non-finite serialization disabled. Optional evaluation telemetry is a JSON record on stderr selected with EXTRACT_TELEMETRY=1; ordinary invocation requires no telemetry. Keep input preparation errors separate from provider errors.

Runtime validation cannot prove that the model read the correct source row. Address that limitation with frozen metrics and manual inspection, not a misleading grounding claim.

### Alternatives and tradeoffs

| Choice | Benefits | Costs/risks | Recommendation |
|---|---|---|---|
| One complete-document request | Smallest code; shared context; one output object; one request/document | Larger payload and output; long reports may exceed limits | Default for this small corpus; explicit failure on limits |
| Per-page requests | Bounded page payload; localized failures | Repeated prompts; aggregation and duplicate risks; more requests/latency; cross-page continuation issues | Defer unless access limits block full-document requests; if used, complete all pages or fail |
| Direct vision | One path for scans, photos and digital PDFs; preserves layout | Resolution-sensitive; image input cost | Use for assessment |
| Digital-PDF text branch | Can reduce image cost; exact digital text | Reading order/table reconstruction; micro symbols already appear corrupted in diagnostic text extraction | Defer; would add routing and a second failure surface |
| Prompt-only changes | Fast; reduces invention and naming drift | Cannot guarantee response validity or fix local coercion | Necessary, insufficient |
| Deterministic checks | Predictable preservation/shape enforcement | Cannot recover unreadable characters or prove source grounding | Use narrow checks, not heuristic medical repairs |
| Schema-constrained JSON | Less formatting ambiguity | Model/API schema support must be verified; shape is not truth | Preferred when supported, plus local validation |
| Unconstrained JSON/manual parsing | Works with providers lacking schema support | More malformed output | Strict parser with one optional outer fence; explicit failure |

### Resolution selection

Keep 60 DPI through the behavior and all-page checkpoints to isolate changes. Test 150 DPI as the first candidate for the final setting. Do not change JPG resolution in this experiment. An additional 300-DPI comparison tests whether more pixels earn their cost. Choose based on the predeclared rules below; no default claim that 150 or 300 is more accurate. Record the actual chosen resolution in the final README.

### Planned future file changes

| File | Responsibility |
|---|---|
| extract.py | Targeted pipeline, prompt, all-page handling, validation and optional telemetry |
| evaluate.py (new) | CLI runner, offline scoring, fixed normalization/matching, measurements and reports |
| evaluation_cases.json (new) | Frozen aliases, explicit gold adjudications, manually reviewed unlabelled references, uncertainty notes |
| test_evaluate.py (new) | Meaningful offline scoring invariants |
| test_extract.py (new) | Mocked provider/conversion/CLI contracts and preservation tests |
| evidence/ (new later) | Saved raw responses, predictions, errors, usage and metrics; exact names below |
| README.md | Setup, two-page evidence summary, prompts/rationale and decision log |
| .gitignore (new later) | Local environment, caches and secret exclusion |

No requirements.txt change is planned for the primary path. No baseline copy of extract.py is needed: Git retains the unchanged source and saved outputs retain the measured baseline. A fallback provider adapter, if needed, remains a small direct change in extract.py, not an abstraction hierarchy. This checkpoint creates only this PRD and PLAN.md.

## 4. Evaluation protocol to freeze before baseline

### Corpus and label handling

Supplied set: report_01, 02, 03, 05, 06, 08, 09, 11; 138 rows. The four remaining reports are 04, 07, 10 and 12. Treat this as a development set; do not claim an independent held-out result. Six employer-held reports remain unseen.

Before examining baseline predictions, audit supplied labels against the documents. Store discrepancies in evaluation_cases.json with report, row index, field, original value, proposed value, source location and reasoning. Preserve gold/ byte-for-byte. Known entry: report_01, row 14, value, 304000 -> 340000, printed Platelet Count on page one. Do not change other fields in that row without evidence.

Publish two score views using identical algorithms: **supplied-label** and **adjudicated**. Use adjudicated complete-row micro-F1 as the primary decision metric, with the supplied score displayed alongside it. Any later newly discovered discrepancy must be documented, reviewed, and applied retrospectively to every version; it cannot be accepted merely because it raises the final score.

### Row identity and matching

1. Operate within one report. Never match rows across documents.
2. Normalize names with Unicode compatibility normalization, case folding, boundary whitespace trimming and repeated-space collapse. Preserve clinically meaningful qualifiers (fasting/PP, direct/indirect, total/free, urine/serum).
3. Freeze a small explicit alias table from document vocabulary before baseline predictions. Examples: Haemoglobin/Hemoglobin (Hb), MCV/Mean Corpuscular Volume, Hematocrit/Packed Cell Volume (PCV), T3/Triiodothyronine (T3), TG/Serum Triglycerides, FBS/Glucose - Fasting. Table entries and rationale must be recorded, not generated from output to improve a score.
4. Do not globally equate RBC with RBC Count or Albumin with Serum Albumin: urine versus blood/specimen differences matter. Ambiguous mappings stay unmatched and are reported for review.
5. First pair exact normalized names one-to-one, then remaining unambiguous aliases one-to-one. Duplicate occurrences match in source order. Do not choose a pairing using value/unit/range agreement or fuzzy similarity. Log ambiguous duplicate cases for manual diagnosis without silently optimizing the score.
6. A pairing establishes row identity, not row correctness. Assess fields afterward. Keep order compliance as a separate diagnostic so value metrics do not conceal reordered output.

### Field equality and normalization

| Field | Equality rule |
|---|---|
| Name | Exact normalized name or frozen unambiguous alias; also display exact-name fidelity |
| Plain numeric value | Decimal equality of JSON numbers and strictly numeric strings, ignoring harmless trailing zeros; no broad tolerance |
| Grouped numeric value | Remove only syntactically valid Western/Indian digit grouping: 2,29,000 equals 229000; malformed commas remain text |
| Inequality value | Preserve comparator exactly (< differs from <=); compare bound as Decimal; < 0.5 never equals 0.5 |
| Interval value | Compare both endpoints and delimiter semantics; 2-3 never equals 2 or 2.5; whitespace/dash typography may normalize |
| Text value | Unicode/whitespace normalization and case folding; keep + signs and qualifiers; Negative, Nil and Present (+) are distinct |
| Null | Equals null only; empty string, "null" and absent keys are not equivalent |
| Unit | Trim/space normalization and explicit typography aliases only (micro sign µ/Greek μ; documented g/dl -> g/dL). Do not case-fold arbitrary SI units or convert scale |
| Range | Normalize whitespace/dash typography; parse numeric bounds/comparator without losing inclusivity; text comparisons conservative; preserve null |

Do not convert lakh/cumm to /cumm in the primary metric. Such a value/unit pair may be clinically equivalent after conversion, but this assessment measures source fidelity and the conversion changes printed fields. Do not infer a missing range from a normal-value lookup. No physiology-based replacement of implausible source results.

### Metrics and failure accounting

- Let G = number of expected rows; P = predicted rows in valid successful output; M = identity-matched pairs; C = pairs with all four fields correct.
- Coverage precision = M/P; coverage recall = M/G; coverage F1 = 2M/(P+G). This measures result identification, not complete accuracy.
- Complete-row precision = C/P; recall = C/G; F1 = 2C/(P+G). An identity-matched incorrect row contributes one false positive and one false negative for this metric. Unsupported rows are specifically unmatched predictions (P-M), not every complete-row false positive.
- Missing rows = G-M. Field mismatches are separate; do not label a recovered row with a wrong value as simply absent.
- Report field correctness both among matched rows (conditional diagnostic) and over all expected rows (omissions count wrong). Show actual denominators and mismatch examples.
- Report duplicate extra rows, name fidelity, qualifier preservation, missing-range invention counts and order violations. Qualifier denominator is the reviewed expected inequality/interval/qualitative subset, including omitted rows as incorrect.
- Report schema-valid success count, invalid output count, provider failures, parse failures and timeouts separately.
- Failed documents contribute all expected rows as missing and zero correct rows. Preserve any schema-invalid output as evidence; do not give accuracy credit to its rows. Record a separate failure flag so invalid output cannot look like perfect precision.
- For nonempty gold and zero predictions, precision is N/A, recall/F1 are 0. For expected-empty documents, precision/recall/F1 are N/A; report no-result success and extra-row count. Failed empty-document extraction is not a pass.
- Compute micro metrics from summed counts across all eight labelled reports. Macro-F1 averages the eight per-report F1 values, including failures as zero. Publish both, plus every report; report_11 must not conceal regressions elsewhere.
- Do not combine newly authored unlabelled references with the supplied eight in the headline metric.

### Unlabelled document review

Before predictions, manually transcribe and double-check references in evaluation_cases.json. Record page/table/row and uncertainty. Use the same scoring rules, but label these as candidate-authored references, not employer ground truth.

| Report | Expected review focus |
|---|---|
| 04 | Nine renal/glycaemic results; reference ranges and units |
| 07 | Ten liver rows; distinguish printed values from handwriting/circling; explicitly mark any unresolved illegibility |
| 10 | Nine thyroid/renal rows across two columns; units printed inside range cells; shadows |
| 12 | Zero laboratory results; reject medication doses, vitals and advised tests |

Do not force uncertain report_07 characters into a confident label. Publish uncertainty count; score only adjudicated fields in the separate review view and show excluded fields/rows. A visible row with uncertain value still contributes to coverage. Freeze these decisions before model outputs.

### Reproducibility and artifacts

Proposed evaluator interface, implemented later:

- python evaluate.py run --label baseline --output evidence/baseline
- python evaluate.py run --label behavior --output evidence/behavior
- python evaluate.py run --label all-pages --output evidence/all-pages
- python evaluate.py run --label dpi-150 --dpi 150 --reports report_03 report_05 report_06 report_11 --output evidence/dpi-150
- python evaluate.py run --label dpi-300 --dpi 300 --reports report_03 report_05 report_06 report_11 --output evidence/dpi-300
- python evaluate.py run --label final --output evidence/final
- python evaluate.py score --predictions evidence/final --cases evaluation_cases.json
- python evaluate.py compare --before evidence/baseline --after evidence/final

Each run stores twelve (or explicitly selected subset) report_<id>.json prediction files only for successful documents, report_<id>.response.json raw provider bodies if obtained, plus run.json with per-report status/attempts/timing/usage/configuration and metrics.json. A failed output is identified by run.json, never by a fake empty prediction file. Offline score/compare commands perform no provider calls. Record source revision, prompt text/hash, schema/evaluator/cases/report hashes, exact resolved model, generation settings, resolution and dates. Save baseline source revision before editing it.

The runner captures real stdout/exit status for CLI/schema checks. For baseline provider usage capture, use an evaluation-only wrapper around the existing model call to capture its returned HTTP JSON while preserving the identical outgoing request and returned text. Verify unchanged request construction in tests. Baseline total latency includes the real CLI-equivalent extraction path; record any telemetry wrapper overhead/measurement method. Later EXTRACT_TELEMETRY=1 supports the same usage capture without changing stdout. Do not claim known usage if the provider omits it.

### Timing and cost

Use a monotonic timer from start of the extraction process through result/error completion. Record preparation and request timing when available, plus total wall time. Evaluate sequentially with the same ordering and conditions. Keep actual failures and manual reruns; report attempted-report cost and cost per successful report. Save all attempts rather than selecting best outputs.

Publish per-report times, mean, median and observed maximum. With 8–12 samples, avoid a confident p95 or throughput claim. Run baseline/final once across all twelve; use repeated paired diagnostic runs only if quota/time permit and label variability explicitly. Temperature 0 does not guarantee deterministic responses.

Record provider usage categories actually returned: input, output, cached or reasoning/thought tokens as applicable. Reconcile provider-specific billed categories before computing cost; do not double-count reasoning tokens. Record published pricing source, access date, currency and pricing basis later. If usage or rates are missing, mark cost unknown or a clearly qualified estimate, never zero by assumption. Report actual out-of-pocket spend separately from list-price-equivalent cost. Local-model spend may be zero but hardware/energy/runtime assumptions must be stated if used.

Daily projection = 10000 * measured mean cost/report for a declared representative document mix. Example arithmetic only: $0.001/report implies $10/day; $0.01/report implies $100/day; neither is an observed price. Starter mix has 13 pages across 12 files. One-call architecture makes approximately 10000 requests/day (~6.94/min averaged over 24h); per-page requests on that mix imply ~10833 requests/day before retries. Neither establishes quota eligibility. Sequential processing occupies 10000 * mean_latency_seconds / 3600 worker-hours/day; peak traffic, concurrency, tokens and payload limits remain unmeasured. Report baseline/final projections, successful-report cost, retries and mix assumptions.

### Fairness rules

Freeze scorer, aliases and adjudications before baseline. Keep identical reports, model, settings, evaluator, and cost method between paired variants except the declared treatment. Store intermediate outputs so isolated gains can be distinguished from total improvement. Do not alter evaluation to raise a score. If an evaluator bug is discovered, test the fix and rescore every saved variant.

Provider substitution changes the baseline identity. If Gemini default is inaccessible, retain the original source in Git, change only accessible model/provider transport, and establish the substituted baseline before prompt/preparation/cleanup improvements. Compare final to that baseline, not to an invented default-model score. If model changes later, measure a bridge comparison with both original behavior and improved behavior on the new model or declare confounding; never attribute the entire gain to pipeline changes.

## 5. Model strategy and required architectural answers

Starter uses GEMINI_MODEL (default gemini-3.8-flash), GEMINI_API_KEY, Google v1beta generateContent, temperature 0, maxOutputTokens 16000, HTTP timeout 180 seconds (extract.py:19, 55–78). No calls have checked availability. The README's free-tier assertion is unverified.

After approval, use existing accessible credentials without revealing them. Confirm provider/model vision and multi-image support, JSON/schema capability, response contract, current pricing and project limits. A live smoke test is a later explicit execution step. Timebox access work to 15 minutes within checkpoint 2. First fallback: an already accessible vision-capable Gemini model via GEMINI_MODEL. Second fallback: one already accessible provider using a small direct REST adapter. Do not pick a fictitious model name or assume credits. An already running local vision model is acceptable if hardware/latency allows; installing large weights or building infrastructure is outside the default budget. If none is accessible, report the blocker and offline progress; do not fabricate an API baseline.

**RAG:** Do not implement it. The source document contains the required values. Retrieving standard ranges would directly encourage the current invention failure, and lab-template retrieval adds engineering/evaluation overhead. A terminology lookup could aid downstream canonicalization, but source-faithful extraction and a small evaluator alias table address the present task without retrieval infrastructure.

**Fine-tuning:** Do not implement it. Eight imperfect labelled reports cannot support a credible training/validation program across unseen laboratories. Training risks memorizing templates and consumes the time needed for measurement. Fix page omission, representation loss and prompt behavior first; discuss fine-tuning only as a future option with a larger audited dataset and a held-out distribution.

**Multi-step agent:** Do not implement it. The workflow is bounded document conversion, extraction and validation. An agent would add calls, latency, failure paths and uncertain stopping rules without repairing the known deterministic defects. A later targeted verification pass could be tested if measured residual errors justify it; it does not require open-ended agent orchestration.

## 6. Checkpoints and proposed commands

All commands below are future verification commands, not executed in Checkpoint 0. Use the repository root and python mapped to the selected Python 3.10+ environment. Network commands require accessible credentials/budget. A commit occurs only after its acceptance checks and review boundary; no squash. These checkpoints total 235–310 minutes after approval, plus contingency up to 30 minutes. Count already-spent planning time against the overall 4–6 hours; reduce optional repeats/experiments if necessary, not evaluation honesty or required documentation.

### Checkpoint 0 — Requirements review (current)

- **Objective:** agree contract, metrics, architecture, scope and approval boundaries.
- **Files:** create PRD.md and PLAN.md only.
- **Tasks:** inspect supplied materials; record factual defects, decisions and open setup questions; propose checkpoints.
- **Acceptance:** only these two files created; supplied files unchanged; no implementation, calls, tests, installations, Git initialization or commits.
- **Verification:** read both documents; compare starter file hashes and inventory. No application tests.
- **Evidence:** these drafts and current transcript; no claimed scores.
- **Effort:** planning already spent must be counted; no additional implementation estimate.
- **Dependencies:** none for document creation.
- **Git boundary:** none; PLAN.md deliberately uncommitted pending user review.
- **Rollback:** revise drafts during review; preserve the approved PLAN.md after its later commit.

### Checkpoint 1 — Preserve starter and freeze evaluation (55–70 minutes)

- **Objective:** establish trustworthy scoring before extraction changes.
- **Files:** later Git metadata and .gitignore; PRD.md/PLAN.md committed; new evaluate.py, evaluation_cases.json, test_evaluate.py. No extract.py or gold edits.
- **Tasks:** resolve Git provenance. If this is an archive, initialize only after approval, commit supplied starter unchanged, then commit approved PLAN.md/PRD.md before any code. Audit labels and independently transcribe four review references. Implement fixed offline scorer, run manifest shape and no-call score/compare paths. Freeze aliases and correction overlay.
- **Acceptance:** report 01 correction explicit; both score views; one-to-one matches; clinically distinct qualifiers/units not merged; incorrect matched row penalized; missing and extra rows visible; failure/empty conventions tested.
- **Tests/commands:** python -m unittest test_evaluate -v; git diff -- gold reports brief.md schema.json; git log --oneline. Tests cover duplicate predictions, wrong decimal, missing row, invented row/range, comparator loss, null, unit scale, alias ambiguity and zero-row/failure accounting.
- **Evidence:** checked evaluation_cases.json, test output, evaluator revision/hash, manual source-review notes embedded in cases.
- **Dependencies:** approval to begin; Git provenance decision. No model access needed.
- **Git boundary:** unchanged-starter commit if needed; separate plan commit; then `Add fixed extraction evaluation and audited review cases`.
- **Rollback:** revert scorer implementation if incorrect; fix and rescore all variants if a defect is found later. Do not rewrite initial PLAN.md or supplied labels.

### Checkpoint 2 — Provider setup and measured baseline (30–40 minutes)

- **Objective:** capture real unchanged-behavior baseline, costs and failures.
- **Files:** evaluate.py, test_evaluate.py; README.md setup/decision notes; extract.py only if documented model/provider transport substitution is necessary. New evidence/baseline/report_<id>.json and report_<id>.response.json for reports 01–12 where obtained; evidence/baseline/run.json and metrics.json.
- **Tasks:** timebox access verification to 15 minutes; record pricing/quota sources and exact model. Complete runner/usage capture without changing prompt, DPI, page selection or cleanup. Run all twelve; manually inspect errors and identify three categories with examples. Use all reports even if some fail; retain failure records.
- **Acceptance:** baseline source revision preserved; real outputs/statuses for all inputs; both labelled score views and separate manual-review results; actual timing; usage/cost evidence or explicit unknowns; no secret values logged. Substitute baseline clearly named if necessary.
- **Tests/commands:** python -m unittest test_evaluate -v; python evaluate.py run --label baseline --output evidence/baseline; python evaluate.py score --predictions evidence/baseline --cases evaluation_cases.json. One setup smoke extraction may precede the run; count its cost separately.
- **Evidence:** saved predictions/raw responses/run manifest, metrics, three initial error examples and access limitations.
- **Dependencies:** checkpoint 1; usable model/provider and approved spending constraints. No access means this checkpoint is blocked, not passed.
- **Git boundary:** `Record unchanged-behavior baseline and model setup`; separate substitution commit before measured run if needed.
- **Rollback:** preserve baseline evidence; revert only substitution if it fails. Never relabel a failed/default run as a successful baseline.

### Checkpoint 3 — Faithful values, prompt and validation (45–60 minutes)

- **Objective:** remove confirmed representation/invention failures and distinguish failure from no results.
- **Files:** extract.py; new test_extract.py; README.md prompt/decision notes; evidence/behavior/report_<id>.json and report_<id>.response.json where obtained, run.json, metrics.json.
- **Tasks:** replace numeric-only/inference prompt; preserve names/value types and nulls; omit computed status. Implement strict parse/local validation, completion checks, optional telemetry and clear CLI errors. Confirm schema-generation capability before enabling it; document strict JSON fallback if unsupported. Keep first-page/60-DPI preparation unchanged in this checkpoint.
- **Acceptance:** mocked tests preserve Negative, Present (+), 2-3, < 0.5 and 2,29,000; missing ranges stay null; missing key/malformed JSON/truncation fail visibly; schema-invalid results never printed. Report 12 reviewed for zero unsupported results. Live metrics may still show model errors; no automatic claim of correctness.
- **Tests/commands:** python -m unittest test_extract test_evaluate -v; python evaluate.py run --label behavior --output evidence/behavior; python evaluate.py compare --before evidence/baseline --after evidence/behavior.
- **Evidence:** preservation/failure test results, exact revised prompt and raw/field-level before/after errors on 03, 06, 09 and 12.
- **Dependencies:** checkpoint 2; actual provider response/format contract.
- **Git boundary:** `Preserve source values and reject invalid extraction responses`.
- **Rollback:** revert behavior commit if regressions outweigh gains; retain its evidence. No evaluator changes to make it pass.

### Checkpoint 4 — All-page extraction (30–40 minutes)

- **Objective:** remove page-one-only information loss with minimal architecture.
- **Files:** extract.py, test_extract.py; evidence/all-pages/report_<id>.json and report_<id>.response.json where obtained, run.json, metrics.json.
- **Tasks:** render all pages, order numerically, build one multi-image request, bound conversion, clean temporary files and avoid partial success. Preserve 60 DPI to isolate all-page treatment. Add input-format/filesystem/conversion tests.
- **Acceptance:** mocked page 1/2/10 order correct; every converted page is sent once; all-page source coverage proven on report 11; provider failure leaves no success JSON; compare recovery of its 24 page-two rows without assuming all will be correct. Other reports assessed for regressions.
- **Tests/commands:** python -m unittest test_extract -v; python evaluate.py run --label all-pages --output evidence/all-pages; python evaluate.py compare --before evidence/behavior --after evidence/all-pages.
- **Evidence:** request page count/configuration; report 11 page-two row-level comparison; all-report metrics and cost/latency.
- **Dependencies:** checkpoint 3; selected model supports multiple images within verified limits.
- **Git boundary:** `Extract all PDF pages in document order`.
- **Rollback:** revert all-page commit if transport breaks, retaining evidence. If per-page fallback becomes necessary, document a new commit and full-document failure policy rather than silently changing architecture.

### Checkpoint 5 — Controlled resolution experiments (30–40 minutes)

- **Objective:** test whether better resolution earns measurable accuracy/cost tradeoffs; attempt a plausible change that may not help.
- **Files:** extract.py for EXTRACT_DPI override (default unchanged until decision), evaluate.py, test_extract.py; evidence/dpi-150 and evidence/dpi-300 each contain report_03/05/06/11.json and .response.json where obtained, run.json and metrics.json. README.md records experiment decisions. Retain all-pages subset outputs as the 60-DPI control.
- **Tasks:** hold model, prompt, all-page behavior, schema mode, token budget and scorer fixed. Use predetermined diagnostic subset 03, 05, 06, 11. Compare 60 vs 150 DPI, then 150 vs 300 DPI. Measure paired exact-row/field changes, unsupported rows, failures, payloads, usage and latency. Change default only after evidence. At most one paired repeat on this subset if variability or a surprising delta needs confirmation within quota/time.
- **Acceptance:** treatment changes resolution alone; subset/configurations declared before runs; all outcomes retained, including ties/regressions/errors. Choose the lowest DPI among equal complete-row scores with no extra unsupported rows/failures. Higher DPI is eligible only with more correct rows and no increase in unsupported rows/failures; use full-corpus final run as a regression gate. Flag any runtime/cost tradeoff rather than inventing a threshold. Global provider failures are an access blocker, not evidence that a treatment hurt accuracy.
- **Tests/commands:** python -m unittest test_extract test_evaluate -v; python evaluate.py run --label dpi-150 --dpi 150 --reports report_03 report_05 report_06 report_11 --output evidence/dpi-150; repeat command with dpi-300, 300 and evidence/dpi-300; python evaluate.py compare --before evidence/dpi-150 --after evidence/dpi-300. Compare the same four stored all-pages control reports to 150 DPI; do not compare subset aggregate to a full-corpus aggregate.
- **Evidence:** table of 60/150/300 results on identical subset, exact changed rows, token/cost/latency differences and retained setting.
- **Dependencies:** checkpoint 4; API budget; resolution-only configuration override.
- **Git boundary:** `Evaluate PDF resolution tradeoffs`; separate `Select measured PDF rendering resolution` if default changes. Keep experiment history even if reverted.
- **Rollback:** restore previous/default DPI via a normal revert/selection commit, keep measurements. Do not undo faithful-value or all-page fixes based on a resolution-only result.

The brief explicitly asks for an unsuccessful attempt. A failed improvement cannot be guaranteed honestly. 300 DPI is a plausible predeclared diminishing-returns experiment, not a staged failure. If both resolution increases help, report that truth; if time remains, predeclare an additional experiment comparing the same improved 150-DPI pipeline with and without schema-constrained generation on the same subset (only if both are supported). Do not deliberately degrade extraction or label an unrun experiment unsuccessful. If no attempted change fails to help, disclose that deliverable gap instead of manufacturing an outcome. Additional experiments consume contingency and have their own saved configuration/results in evidence/format-unconstrained/{report_<id>.json,report_<id>.response.json,run.json,metrics.json}; no new application module.

### Checkpoint 6 — Final verification and submission evidence (45–60 minutes)

- **Objective:** verify chosen changes across all reports and deliver a concise explainable assessment.
- **Files:** README.md; evidence/final/report_<id>.json and report_<id>.response.json where obtained for reports 01–12; run.json, metrics.json; evidence/comparison.json. Optional transcripts only if user elects export and reviews secret exposure. Implementation files change only for newly reproduced defects, with focused tests and a separate fix commit.
- **Tasks:** run full offline suite and all twelve final extractions; compare stored baseline using the frozen evaluator; manually review unlabelled outputs and three strongest root-cause examples. Report supplied/adjudicated micro/macro scores, failures, cost, latency, exact model, prompts, unsuccessful experiment (or honest gap), daily-scale assumptions, limitations, RAG/fine-tuning/agent paragraphs and decision log. Keep README within two pages. Confirm baseline/final evidence can be rescored without credentials.
- **Acceptance:** successful CLI results schema-valid; all targeted local defects have regression coverage; final primary adjudicated micro-F1 exceeds baseline and macro-F1 does not regress; no increase in manually confirmed unsupported results on 12 or invented missing ranges on 03. If these empirical gates fail, diagnose/revert within remaining time and report the actual outcome; never mark improvement proved. Small-set results are not generalization guarantees. All submission requirements accounted for; secrets absent; original plan and supplied assets unchanged.
- **Tests/commands:** python -m unittest discover -p 'test_*.py' -v; python evaluate.py run --label final --output evidence/final; python evaluate.py compare --before evidence/baseline --after evidence/final; python evaluate.py score --predictions evidence/final --cases evaluation_cases.json; git diff -- gold reports brief.md schema.json PLAN.md; git log --oneline. Manual inspect report_11 second-page coverage and reports 03/06/09/12. Hash comparison against starter snapshot verifies fixtures; a clean git diff alone does not prove original bytes.
- **Evidence:** runnable eval, baseline/final outputs, comparison.json, test results, per-report tables, manual findings, measured/qualified cost and latency, two-page README and real history.
- **Dependencies:** checkpoints 1–5, or explicitly recorded provider/resource constraints. No declaration of completion without empirical evidence.
- **Git boundary:** `Document final extraction evaluation and engineering decisions`; any necessary bug fix precedes it as a separate tested commit. Do not squash.
- **Rollback:** choose a better measured prior configuration and rerun final; preserve experiment/failure evidence. Leave unverified claims out of submission.

## 7. Acceptance and time-management summary

Product acceptance: source-faithful values and nulls, all pages sent, stable CLI, valid success JSON and explicit failure behavior. Engineering acceptance: focused offline tests pass, honest raw evidence, immutable original assets/plan, explainable commits. Assessment acceptance: runnable frozen eval, baseline/final comparisons, three root causes, costs/latency, unsuccessful attempt or disclosed gap, exact prompts and required tradeoff answers.

Do not invent a numerical target before measuring baseline. The empirical release gates are directional and include regression checks, not a promise of perfect accuracy. If access problems consume the timebox, finish offline correctness work and report live evaluation as blocked. Do not keep expanding scope to recover a perfect score. Cut optional repeats and optional experiments before cutting final evidence or documentation. Reserve the final 45 minutes for verification and README.

## 8. Decisions proposed for approval and unresolved blockers

Proposed decisions: source names/units retained; textual values allowed; missing fields represented by explicit null; no inferred status/ranges; non-lab document returns empty tests; validation failures have nonzero exit and empty stdout; one multi-image vision request; small local schema validator; conservative frozen evaluator aliases; original/adjudicated views; no RAG/training/agents.

Unresolved external/setup facts:

1. Is an original Git repository available, or should the extracted starter become a new repository after approval?
2. Which credentials/model/provider are accessible, with what spend cap, quota and permitted document handling? No credential values should be provided in chat.
3. When was the assessment received, and how much of the 4–6-hour budget has already been spent?
4. Can the accessible model accept multiple images and schema-constrained JSON? If not, select and document the specified fallback before measuring baseline.
5. Should agent transcripts be exported for submission? They are optional and must not expose secrets.

Remaining evidence questions, resolved in later checkpoints: exact baseline failure ranking; full label audit; ambiguous report_07 characters; actual cost/latency; DPI treatment outcome; whether any honest experiment fails to help. These are not blockers to writing the plan, but they are blockers to claiming measured success.

Stop here. Review PRD.md and PLAN.md before approving Checkpoint 1. PLAN.md must be committed before evaluator or extractor code is written; it is deliberately not committed in Checkpoint 0.
