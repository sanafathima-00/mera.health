# Optional local UI

This is a user-requested convenience interface added after assessment finalization.
The original assignment excluded UI work. Keep this distinction clear during review.

Run from the repository root:

```powershell
$env:GEMINI_MODEL = 'gemini-3.6-flash'
python ui_server.py
```

Open http://127.0.0.1:8765. Upload your own PDF, JPG/JPEG or PNG (up to 32 MB),
then click Extract results. All PDF pages go through the existing extractor.
The app displays test names, values, units and reference ranges; search and JSON
download work locally. It does not calculate clinical flags or interpret results.

The server loads the ignored project-local `.env` and overrides any stale process
key. Nothing is sent until you click Extract. That click sends the document to
Google Gemini: use documents you are authorized to share with that provider.
Provider terms, availability, quota and billing remain your project's responsibility;
this interface does not verify free-tier eligibility or guarantee zero cost.

Uploaded files are removed after processing or failure. Results live in the browser
until refresh; no history/database is maintained. This is a localhost-only prototype,
not a hosted medical application. It checks file suffix/signature, limits request
size, requires same-origin upload tokens and permits one extraction at a time.
Malformed files or provider failures appear as errors, not fabricated results.

The original `python extract.py <file>`, schema, labels, evaluator and assessment
evidence remain unchanged. No extra dependencies are needed. Startup and UI testing
make no model calls; browser-driven tests use synthetic responses. Real extraction
success still depends on model access, document legibility and provider reliability.
