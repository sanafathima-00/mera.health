# Checkpoint 5 preparation — no generation executed

## Reproducible protocol

`experiment.py` loads `extract.py` with `git show` into separate modules:

- Original: df3de423ac889a084b0cd7fd02a04f5d1c95dc29.
- Improved: 9933806ac76fe1efc951c2ec77f42334065d71d5.

Historical files, commits and current extraction implementation are not edited.
Only module globals MODEL and DPI are overridden in memory. The observer returns
successful response bytes unchanged and does not repair predictions. It records
raw extraction text, provider response bytes, usage and latency. Error messages
are classified without persisting arbitrary provider messages, headers or keys.

| Order | Report | Versions | DPI | Purpose |
|---|---|---|---|---|
| 1–2 | 06 | original, improved | 60 | Qualitative results, inequalities, intervals |
| 3–4 | 11 | improved, original | 60 | All-page coverage versus historical first-page behavior |
| 5–6 | 03 | original, improved | 60 | Missing reference ranges |
| 7–8 | 08 | improved, original | 60 | Printed names and Direct qualifier; restrictive frozen matching |
| 9–10 | 11 | improved only | 150, 300 | Resolution treatment, reusing improved 60-DPI control |

Report 06 must produce two schema-valid outputs before later pairs proceed.
DPI treatments require schema-valid improved report 11 at 60 DPI. At most ten
generation calls; no retries or substitutions. Stop immediately for authentication,
billing, quota or permission errors, or after two consecutive HTTP 503 responses.
Failed later pairs do not enter extraction-quality comparisons. Transport failure
latency and reliability remain separate from extraction quality.

Every request is inspected before sending: exact gemini-3.6-flash endpoint,
temperature 0, maxOutputTokens 16000, timeout 180 seconds, image parts followed
by one expected prompt. Effective prompt text/hash, image count/ordered image
hashes, revision/source hash and DPI are saved. Original and improved prompts
intentionally differ. Improved multi-page requests include the documented page
prefix; original stays single-page. Resolution changes only the improved module's
DPI global, keeping prompt, parsing, page handling and generation settings fixed.
The historical original renderer has no conversion timeout; no timeout is added
by the runner, to preserve its behavior. Provider default thinking settings are
not overridden; resolved response model version is recorded when exposed.

## Commands and evidence

Safe preparation and tests (no model calls):

```powershell
python -B experiment.py
python -B -m unittest discover -p 'test_*.py' -q
```

Future execution, only after explicit generation approval and verified prerequisites:

```powershell
python -B experiment.py --generate --preflight <reviewed-preflight.json> --output evidence/checkpoint5/<new-run-id>
```

No reviewed preflight file exists yet. It must record model, authentication_verified,
project_association_verified, free_tier_verified, quota_available_verified and
generation_approved as true; verified_at_unix within one hour; credential_sha256
matching the current local key; project_id, association_evidence and quota_evidence.
These fields are a documented operator gate, not an independent billing/quota API.
Do not populate them from assumptions. The runner loads ignored `.env`, handles
surrounding quotes/whitespace, and temporarily overrides the stale process key.
Neither key nor request authentication headers are written. No metadata request is
automatically performed by the harness.

The destination must not exist. Per treatment: prediction JSON, raw model text,
successful provider response, sanitized attempt JSON, evaluator-compatible run.json
and unedited frozen-evaluator metrics. Root run.json contains reliability/latencies,
usage, stopping reason, valid-pair-only original/adjudicated row diagnostics and
micro/macro aggregates. Partial-corpus evaluator outputs retain their explicit
availability status; failure-inclusive scores are not extraction accuracy.
Policy, schema and original gold fingerprints must remain identical throughout.
Historical evidence is never overwritten. Synthetic evidence exists only inside
automatically removed test directories.

Cost estimates remain null until current pricing and token accounting are verified.
Failure usage is unavailable, not zero. Per-success paid-equivalent estimates,
daily projection and resolution conclusions need actual successful requests;
there is no live quality, latency, usage or cost improvement evidence yet.

Important historical limitation: malformed model text can become a schema-valid
empty extraction in the original implementation. Raw text and finish reasons make
this visible. A valid schema is not proof of a valid source extraction. Do not
rewrite original behavior to hide this defect or interpret mock scores as accuracy.

## Read-only credential/project investigation, 8 October 2026

Earlier metadata-only GET authenticated the local key with HTTP 200 for
models/gemini-3.6-flash and listed generateContent. No further authentication or
generation request was made during this preparation.

AI Studio's API Keys page shows a masked key under `mera health take home`,
project `gen-lang-client-0610041060`, marked Free tier. Its displayed suffix
matches the local key in a private comparison; the other visible project's suffix
does not. No key or suffix is included here. This is supportive association evidence,
not an exact full-key lookup; masked identifiers can collide.

Following View usage for that key selects the intended project and shows Free tier,
but usage charts report Error loading data. Project Rate Limit displays No usage
data available, including with All models selected. Neither Gemini 3.6 Flash limits
nor current consumption/headroom are shown. Empty data does not mean unused quota.
No billing, key creation, project import or project settings were changed.

An exact association can be obtained with Google's read-only
[API Keys lookupKey method](https://docs.cloud.google.com/api-keys/docs/get-info-api-keys):
it returns the owning project number using authorized Google Cloud credentials.
The documented request puts the key in a query parameter; do not paste it into a
browser URL, shell argument or log. A future authenticated client must suppress
request logging. gcloud was not found and the standard Windows ADC file was absent;
no installation, login or credential expansion was attempted.

Project-specific quota can be investigated through AI Studio or the read-only
[Service Usage quota metrics API](https://docs.cloud.google.com/service-usage/docs/reference/rest/v1beta1/services.consumerQuotaMetrics/list),
which needs appropriate OAuth/IAM access. Configured limits alone are not live
remaining quota; usage must also be verified. Google's
[Gemini rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits)
directs users to their active project limits in AI Studio. Generic model metadata
and advertised free-tier pricing cannot establish this project's usable quota.

**Remaining blockers:** exact key-to-project verification and project-specific
Gemini 3.6 Flash free-tier eligibility/available quota. Generation stays blocked.

## Offline verification

Harness tests cover historical revision loading, source/prompt differences,
serialized settings equality, ordered multi-image request construction, alternating
pair order, DPI rendering and cleanup, ten-call bound, secret-free evidence,
frozen scoring, provider categories, first-pair and DPI gates, consecutive 503
stop, stale environment override, safe default CLI, blocked generation and
existing-directory protection. All network responses are synthetic.

Executed `python -B -m unittest discover -p 'test_*.py' -q`: 86 passed,
zero failed (12 harness tests plus 74 existing tests). Safe plan command reports
zero generation calls. Protected tracked files and historical evidence have no
diff. `.env` remains ignored/untracked. An existing untracked preflight evidence
directory was preserved and is not included in the preparation commit.
