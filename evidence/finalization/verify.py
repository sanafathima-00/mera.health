"""Offline packaging verification. Does not print secrets or make model calls."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
START = "52f3a3cdcbf2e040b38751c44f3e64c064399dd9"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def unchanged(revision, paths):
    return not git("diff", "--name-only", revision, "--", *paths).strip()


def main():
    result = {}
    tests = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                            "-p", "test_*.py", "-q"], cwd=ROOT, capture_output=True, text=True)
    result["tests"] = {"exit_code": tests.returncode, "output": tests.stderr.strip()}
    result["protected"] = {
        "starter_assets": unchanged("df3de42", ["PLAN.md", "brief.md", "schema.json", "reports", "gold"]),
        "frozen_evaluator": unchanged("c2e319f", ["evaluate.py", "evaluation_cases.json", "EVALUATION.md"]),
        "extractor": unchanged("9933806", ["extract.py"]),
        "historical_evidence": unchanged(START, ["evidence/baseline", "evidence/baseline_36",
            "evidence/submission", "evidence/recovery_38_report01_20261008T113520Z",
            "evidence/fallback_36_report01_20261008T114344Z", "evidence/fallback_36_report01_20261008T114807Z",
            "evidence/checkpoint5_preflight_20261008T143151269419Z",
            "evidence/checkpoint5_single_probe_preflight_20261008T144859945411Z",
            "evidence/checkpoint5_single_probe_20261008T145238124815Z"]),
        "prompt_document": unchanged(START, ["PROMPTS.md"]),
    }
    result["evaluation"] = {}
    for directory in ("baseline", "baseline_36", "checkpoint5_single_probe_20261008T145238124815Z"):
        run = subprocess.run([sys.executable, "-B", "evaluate.py", "score", "--predictions",
                              "evidence/" + directory], cwd=ROOT, capture_output=True, text=True)
        current = json.loads(run.stdout)
        saved = json.loads((ROOT / "evidence" / directory / "metrics.json").read_text())
        result["evaluation"][directory] = {"exit_code": run.returncode,
            "views_unchanged": current["views"] == saved["views"],
            "counts_unchanged": current["report_status_counts"] == saved["report_status_counts"]}
    plan = subprocess.run([sys.executable, "-B", "experiment.py"], cwd=ROOT, capture_output=True, text=True)
    result["experiment"] = {"exit_code": plan.returncode, "generation_calls": json.loads(plan.stdout)["generation_calls"]}
    render = json.loads((Path(__file__).parent / "readme_render.json").read_text())
    result["readme"] = {"pages": render["pages"], "hash_matches": render["readme_sha256"] ==
                         hashlib.sha256((ROOT / "README.md").read_bytes()).hexdigest()}
    patterns = [rb"AIza[0-9A-Za-z_-]{35}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"gh[pousr]_[A-Za-z0-9]{30,}", rb"github_pat_[A-Za-z0-9_]{30,}"]
    # Exact local key comparison stays in memory; never write key or matching text.
    from experiment import local_key
    try:
        key = local_key(ROOT / ".env").encode() if (ROOT / ".env").exists() else None
    except ValueError:
        key = None  # Placeholder/missing key is not required for offline verification.
    def secret(data):
        return bool((key and key in data) or any(re.search(pattern, data) for pattern in patterns))
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    matches = [name for name in files if name and secret((ROOT / name).read_bytes())]
    historical_matches = []
    for line in git("rev-list", "--objects", "--all").decode().splitlines():
        oid = line.split(" ", 1)[0]
        if git("cat-file", "-t", oid).strip() == b"blob" and secret(git("cat-file", "blob", oid)):
            historical_matches.append(oid)
    result["secrets"] = {"candidate_matching_files": matches, "historical_matching_blobs": len(historical_matches),
                         "env_ignored": subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT).returncode == 0,
                         "env_untracked": not git("ls-files", ".env").strip()}
    result["unexplained_deletions"] = git("diff", "--name-only", "--diff-filter=D", START).decode().splitlines()
    result["scope"] = "Offline finalization; no generation, publication or submission"
    (Path(__file__).parent / "verification.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, indent=2))
    valid = (tests.returncode == 0 and all(result["protected"].values()) and
             all(v["views_unchanged"] and v["counts_unchanged"] for v in result["evaluation"].values()) and
             result["readme"]["pages"] <= 2 and result["readme"]["hash_matches"] and
             not matches and not historical_matches and not result["unexplained_deletions"])
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
