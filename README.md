# Lab-report extractor: final assessment

**Result:** cleanup, validation and all-page PDF input are verified offline. Live accuracy improvement is **unproven**. Nineteen generation attempts produced two valid original predictions and 17 failures; no improved prediction exists. Generation is paused. This is a prototype, not a clinically validated product.

## Setup and reproduction

Python 3.10+ and Poppler (`pdftoppm` on PATH); no Python packages required. Install Poppler with `brew install poppler` (macOS), `sudo apt-get install poppler-utils` (Debian/Ubuntu), or add extracted Windows Poppler `Library/bin` to PATH. Configure the key privately in ignored `.env`, following `.env.example`; exclude `.env` from any ZIP. The extractor does not automatically load it.

```powershell
pdftoppm -v
$env:GEMINI_MODEL = 'gemini-3.6-flash'
# GEMINI_API_KEY must be configured in this process:
python extract.py <path-to-report>
# Offline: no credentials or provider calls:
python evaluate.py score --predictions evidence/baseline_36
python -B -m unittest discover -p 'test_*.py' -q
```

Run commands from the repository root. Evaluator exit 1 means recorded failures/invalid outputs, 2 unavailable predictions, 3 evaluation error; baseline exit 1 is expected. No pip install is needed. Optional post-assessment upload UI: [UI.md](UI.md).

When generation is authorized, load `.env` for one CLI invocation without printing the key:

```powershell
python -c "import os,subprocess,sys; from pathlib import Path; from experiment import local_key; os.environ['GEMINI_API_KEY']=local_key(Path('.env')); sys.exit(subprocess.call([sys.executable,'extract.py',sys.argv[1]]))" reports/report_01.pdf
```

The loader handles surrounding quotes/whitespace and overrides stale process credentials. Explicitly select 3.6; source default remains 3.8. Success prints schema-valid JSON; failures exit nonzero. AI Studio displays Free tier; billing-link status and remaining quota are unverified. No billing was enabled.

## Architecture and three diagnoses

PDF -> every ordered PNG page at 60 DPI -> one Gemini vision request -> strict JSON/row validation -> preserved source values. JPG/PNG bytes are unchanged. Temperature 0, maxOutputTokens 16000, network timeout 180 seconds; rendering timeout 60 seconds with temporary cleanup. No retries, OCR branch or per-page orchestration. Preserve meaningful strings/finite numbers/nulls; reject malformed output and incomplete provider responses. Actual prompts and rationale: [PROMPTS.md](PROMPTS.md).

| Example | Original root cause | Fix and evidence |
|---|---|---|
| 06: Colour Dark Yellow, Sugar Present (+), Leucocytes 2-3, CRP <0.5 | Float coercion loses meaningful strings | Preserve strings; offline regressions pass; no live prediction |
| 03: T3, T4, Glycated Hb missing ranges | Prompt explicitly invents standard ranges | Source-only ranges/nulls; live prompt effect unmeasured |
| 11: 24 labelled rows on page two | Original rendering sends page one only | Both pages reach one mocked request; live recovery unmeasured |

Validation proves shape, not source truth. Multiple images increase memory/payload; 60 DPI may miss fine print. Higher resolution and constrained generation were not tested live. No clinical corrections or unit conversions are performed.

## Frozen evaluation and results

[EVALUATION.md](EVALUATION.md): one-to-one exact/frozen-alias matching; duplicates in source order; conservative Decimal normalization; preserve inequalities/intervals; no incompatible unit conversion. Report missing, unmatched, invalid, failed and unavailable separately. Report 01 platelet is document 340000 versus supplied 304000: publish original and explicit adjudicated views without changing gold.

| Original Gemini 3.6 baseline | Original labels | Adjudicated |
|---|---:|---:|
| Report 01 complete F1; 14/14 matched | 92.86% | 100% |
| Report 08 complete F1; 1/6 matched | 16.67% | 16.67% |
| Eight-attempt complete micro P/R/F1 | 70%/10.14%/17.72% | 75%/10.87%/18.99% |
| Eight-attempt complete macro F1 | 13.69% | 14.58% |

**Failure-inclusive aggregates are operational results, not extraction accuracy.** Six baseline requests failed (five 503, one timeout). Valid outputs: 15 matched rows; values correct 14/15 original, 15/15 adjudicated; units/ranges correct on those matches. Report 08 loses the LDL Direct qualifier and expands names; five unmatched identities do not prove hallucinations. [BASELINE_36.md](BASELINE_36.md) and saved metrics give all per-report fields, coverage, 123 missing rows and five unmatched predictions. Improved/paired accuracy is unavailable.

## Reliability, unsuccessful work and cost

Eight original 3.8 calls failed 503. Two approved backoff/jitter retries also failed: **0/2 successes**, 2.943/2.870-second attempts plus 12.417/24.307-second waits. This unsuccessful access recovery produced no extraction evidence. The 3.6 fallback succeeded; seven further original calls produced one success. Improved Report 06 failed transport after **181.100 seconds**, before an HTTP response was obtained; phase timings and underlying transport cause are unknown. No valid pair or 150/300-DPI experiment exists. See [EXPERIMENTS.md](EXPERIMENTS.md).

Original 3.6 attempt time: 398.863 seconds, mean 49.858; successful mean 9.206. Two successes expose 2484 input, 1258 output and 2521 thinking tokens (6263 total). Rates verified 8 October 2026: $0.75/M input, $3.75/M output including thinking. Paid-equivalent mean **$0.008017/report**, not invoice spend. Multiplying this narrow sample by 10000 gives **$80.17/day**, not a representative forecast. Failed usage, final cost and production quota are unknown; Free tier does not establish 10000/day capacity.

## Scope, review and limitations

**RAG:** the document contains the requested data. Retrieving standard ranges encourages the invention failure; no retrieval service is needed for source extraction.

**Fine-tuning:** eight imperfect labelled reports cannot support credible training/generalization across labs. Larger audited held-out data is needed before training.

**Agent:** conversion, one request and validation are bounded steps. Extra calls add latency, cost and failure paths without fixing deterministic value loss.

Offline visual assessment: 04 clean printed PDF; 07 scanned PDF with handwriting; 10 shadowed phone photo; 12 prescription/advised tests. All inputs are supported; no predictions, new labels or accuracy claims. Details: [UNLABELLED_REVIEW.md](UNLABELLED_REVIEW.md).

Decision log: preserve initial 255-word PLAN (df3de42); freeze evaluator (c2e319f); select 3.6 only after approved fallback; reject post-hoc aliases/fabricated scores; separate cleanup and page commits; pause generation after bounded failure. **94 offline tests pass**, including Decimal serialization and seven mocked UI tests. Mandatory measured before/after improvement and an unsuccessful extraction-quality experiment remain unmet. History and safe evidence are included; optional transcripts are absent. See [FINALIZATION.md](FINALIZATION.md) for packaging and publication status.
