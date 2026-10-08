# Initial implementation plan

Checkpoint 0 draft, 8 October 2026. Uncommitted; implementation has not started. After review, commit this plan before code and preserve it unchanged. Log later decisions in the README.

Within a 4–6-hour total budget, first preserve the starter in Git and freeze an evaluation. Audit eight labelled reports and separately review four unlabelled reports. Preserve supplied labels; document report 01's platelet discrepancy (document 340000, gold 304000). Report supplied-label and adjudicated scores.

Measure unchanged extraction behavior on an accessible vision model before improvements. Try supplied Gemini first; access, quota and prices are unverified. Document substitutions. Save outputs, failures, configuration, usage, cost and latency. Use fixed one-to-one matching and conservative normalization; report row precision/recall/F1, field errors, omissions and unsupported rows.

Keep `python extract.py <file>`. Send all ordered PDF pages in one vision request. Preserve printed names, textual/numeric results, inequalities, intervals, units and ranges; use null for missing information. Exclude medications, vitals and advised tests without results. Request constrained JSON where supported; validate locally and fail visibly.

I expect page omission, numeric coercion and invented ranges to dominate; verify that against baseline evidence. Commit behavior fixes separately from all-page handling. Compare 60/150/300 DPI on a fixed subset. Retain the simplest measured setting; do not assume higher resolution helps or manufacture a failed experiment.

Finish with baseline/final evidence, three report/row root causes, an unsuccessful experiment if observed, daily cost projection and a two-page README with prompts, decisions and RAG/fine-tuning/agent arguments. Reserve time for tests/documentation. Avoid platform work. Resolve access, Git provenance and remaining time before execution.
