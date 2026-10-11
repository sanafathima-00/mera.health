"""Render current README separately, preserving the historical submission render.

Uses the same ReportLab/pypdf documentation-only dependencies and layout.
"""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("readme_renderer", HERE.parent / "submission/render_readme.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
renderer.OUT = HERE
if __name__ == "__main__":
    renderer.main()
    record = json.loads((HERE / "readme_render.json").read_text())
    record["renderer"] = "evidence/finalization/render_readme.py (historical layout reused)"
    (HERE / "readme_render.json").write_text(json.dumps(record, indent=2) + "\n")
