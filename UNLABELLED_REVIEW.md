# Offline review of unlabelled inputs

8 October 2026. Direct visual inspection only; no predictions or reference labels
were created. These four reports stay outside the frozen eight-report metrics.
PDF page counts were checked with pdfinfo. PDF pages were rendered at 100 DPI for
human inspection, independently of the unchanged extractor's 60-DPI setting.

| Report | Format / pages | Observed characteristics | Extraction challenges | Input support |
|---|---|---|---|---|
| 04 | PDF, 1 page | Clean digital printed renal/glycaemic tables; extractable text; no visible handwritten annotations | Small monospaced text, separate flag/unit/range columns, Na+/K+/Cl- names and fasting/PP qualifiers, inequality reference range | Supported; rendered to one PNG by current pipeline. Model accuracy unmeasured |
| 07 | PDF, 1 page | Image-based printed liver table with scan grain, mild skew, handwritten circle and a repeat-test/review note; pypdf finds no text | Circle overlaps printed rows; small decimal/unit text; distinguish clinician advice from completed results; do not repair inconsistent-looking values | Supported through vision rendering, without a text/OCR branch. Accuracy on annotation/occlusion unmeasured |
| 10 | JPG, single image (PDF page count not applicable) | Photo of printed thyroid/kidney tables, perspective distortion, vertical shadow and soft text; no visible handwriting | Multiple side-by-side tables, units embedded in reference-range column, TSH (Ultrasensitive) qualifier and specimen prefixes, faint small text and column association | JPG bytes supported unchanged; no deskew, cropping or shadow correction. Accuracy unmeasured |
| 12 | JPG, single image (PDF page count not applicable) | Photograph of a printed prescription with vitals, medication doses and investigations advised; no visible handwriting | Distinguish numbers/doses/vitals from lab results and ordered tests from completed tests. Visual review found no reported laboratory results | Input supported; prompt explicitly excludes prescriptions/vitals/advised tests. An empty tests array is the intended behavior, not a measured model output |

This assessment records format support and observed document difficulty, not
recovered result counts, model accuracy or newly authored ground truth. The brief
states patients are fictional; review notes deliberately omit patient identifiers.
Poppler emitted a Symbol-font warning for report 04 during review rendering; the
page rendered and was inspected. Character fidelity across other environments is
not established by this single visual check.
