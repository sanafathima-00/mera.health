"""Render this README's Markdown subset locally with ReportLab; no network access.

Requires ReportLab and pypdf only for documentation rendering, not extraction.
Run from any directory with a Python environment providing those packages.
"""
import hashlib
import json
import re
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
body = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=12, spaceAfter=5)
title = ParagraphStyle("title", parent=body, fontName="Helvetica-Bold", fontSize=15, leading=18, spaceAfter=8)
heading = ParagraphStyle("heading", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=14, spaceBefore=7, spaceAfter=4, keepWithNext=True)
cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=11, spaceAfter=0)
code = ParagraphStyle("code", fontName="Courier", fontSize=7.5, leading=9, spaceAfter=5)


def inline(s):
    s = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1 (\2)", s)
    s = escape(s)
    s = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', s)


def footer(canvas, doc):
    canvas.setFont("Helvetica", 8)
    canvas.drawString(36, 22, "mera.health assessment | README.md")
    canvas.drawRightString(A4[0] - 36, 22, str(doc.page))


def main():
    data = (ROOT / "README.md").read_bytes()
    lines = data.decode("utf-8").splitlines()
    flow, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.extend(textwrap.wrap(lines[i], width=113, replace_whitespace=False, drop_whitespace=False) or [""])
                i += 1
            flow.append(Preformatted("\n".join(block), code))
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                values = [v.strip() for v in lines[i].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", v) for v in values):
                    rows.append([Paragraph(inline(v), cell) for v in values])
                i += 1
            table = Table(rows, colWidths=[(A4[0]-72)/3]*3, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0),colors.HexColor("#e8eef3")),
                                       ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#bac4cc")),
                                       ("VALIGN",(0,0),(-1,-1),"TOP"),
                                       ("LEFTPADDING",(0,0),(-1,-1),5), ("RIGHTPADDING",(0,0),(-1,-1),5)]))
            flow.extend([table, Spacer(1,5)])
        elif line.startswith("#"):
            flow.append(Paragraph(inline(line.lstrip("# ")), title if line.startswith("# ") else heading))
            i += 1
        else:
            paragraph = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "```")):
                paragraph.append(lines[i]); i += 1
            flow.append(Paragraph(inline(" ".join(paragraph)), body))
    pdf = OUT / "README.pdf"
    SimpleDocTemplate(str(pdf), pagesize=A4, leftMargin=36, rightMargin=36,
                      topMargin=32, bottomMargin=34, title="Lab-report extractor final assessment",
                      author="mera.health take-home submission").build(flow, onFirstPage=footer, onLaterPages=footer)
    pages = len(PdfReader(pdf).pages)
    record = {"readme_sha256":hashlib.sha256(data).hexdigest(), "pages":pages,
              "page_size":"A4", "body_font":"Helvetica 10pt / 12pt leading",
              "margins_points":{"left":36,"right":36,"top":32,"bottom":34},
              "renderer":"evidence/submission/render_readme.py", "scope":"Full README content; no forced page breaks or omitted sections"}
    (OUT / "readme_render.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record))
    if pages > 2:
        raise SystemExit("README exceeds two pages; shorten the source")


if __name__ == "__main__":
    main()
