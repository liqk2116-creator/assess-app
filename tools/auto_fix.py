import os
import re
import sys
import subprocess
from pathlib import Path

# ---- safety settings ----
MAX_ATTEMPTS = 2
MAX_DIFF_LINES = 3000
FORBIDDEN_PREFIXES = [
    ".github/workflows/",
]
ALLOWED_APPLY_TOOL = "git"


def run(cmd: list[str], check=True, capture=True, text=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=text)


def git(*args: str, check=True) -> subprocess.CompletedProcess:
    return run([ALLOWED_APPLY_TOOL, *args], check=check)


def get_last_commit_message() -> str:
    return git("log", "-1", "--pretty=%B").stdout.strip()


def count_attempts_from_history() -> int:
    # count recent auto-fix commits on main (best-effort)
    out = git("log", "-20", "--pretty=%B").stdout
    return len(re.findall(r"\[auto-fix\]", out))


def find_referenced_files(log_text: str) -> list[Path]:
    # collect candidate paths like app/xxx.py or tests/xxx.py
    paths = set()
    for m in re.findall(r"([a-zA-Z0-9_\-./\\]+\.py)", log_text):
        p = m.replace("\\", "/")
        if p.startswith("app/") or p.startswith("tests/") or p.startswith("tools/"):
            paths.add(p)
    existing = []
    for p in sorted(paths):
        fp = Path(p)
        if fp.exists() and fp.is_file():
            existing.append(fp)
    return existing[:12]


def read_file_limited(p: Path, max_chars=12000) -> str:
    try:
        s = p.read_text(encoding="utf-8")
    except Exception:
        s = p.read_text(errors="ignore")
    if len(s) > max_chars:
        return s[:max_chars] + "\n\n# ... truncated ..."
    return s


def build_prompt(pytest_log: str, files: list[Path]) -> str:
    ctx_parts = []
    for fp in files:
        ctx_parts.append(f"--- FILE: {fp.as_posix()} ---\n{read_file_limited(fp)}\n")
    ctx = "\n".join(ctx_parts)

    return f"""You are an expert engineer.
Goal: fix the failing tests.

Rules:
- Output ONLY a unified diff patch (git apply compatible). No explanations.
- Do NOT modify any paths under: {FORBIDDEN_PREFIXES}
- Keep changes minimal.
- Do not delete tests to make them pass; fix code properly.
- If you need to add files, include them in the diff.

Pytest failure log:
<<<LOG
{pytest_log}
LOG>>>

Relevant project files:
<<<FILES
{ctx}
FILES>>>
"""


def call_openai(prompt: str) -> str:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY env var/secret.")

    model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

    # Use official OpenAI python package. Compatible with recent versions.
    from openai import OpenAI  # type: ignore
    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        input=prompt,
    )
    text = resp.output_text
    return text.strip()


def ensure_patch_safe(patch: str):
    lines = patch.splitlines()
    if len(lines) > MAX_DIFF_LINES:
        raise RuntimeError(f"Patch too large: {len(lines)} lines")

    # detect file paths in diff headers
    touched = set()
    for ln in lines:
        if ln.startswith("+++ b/") or ln.startswith("--- a/"):
            path = ln.split(" ", 1)[-1].strip()
            path = path.replace("a/", "").replace("b/", "")
            touched.add(path)

    for p in touched:
        for pref in FORBIDDEN_PREFIXES:
            if p.startswith(pref):
                raise RuntimeError(f"Patch touches forbidden path: {p}")


def apply_patch(patch: str):
    tmp = Path(".__autofix.patch")
    tmp.write_text(patch, encoding="utf-8")
    try:
        git("apply", str(tmp))
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


def run_tests() -> bool:
    p = run([sys.executable, "-m", "pytest", "-q"], check=False)
    return p.returncode == 0


def main():
    if len(sys.argv) != 2:
        print("Usage: python tools/auto_fix.py <pytest_log_file>")
        return 2

    # guard: prevent endless loops on main
    if count_attempts_from_history() >= MAX_ATTEMPTS:
        print(f"auto-fix: reached MAX_ATTEMPTS={MAX_ATTEMPTS}, stop.")
        return 0

    log_path = Path(sys.argv[1])
    pytest_log = log_path.read_text(encoding="utf-8", errors="ignore")

    refs = find_referenced_files(pytest_log)
    prompt = build_prompt(pytest_log, refs)

    patch = call_openai(prompt)

    # Basic sanity: must look like a diff
    if "diff --git" not in patch and not patch.startswith("--- "):
        raise RuntimeError("Model did not return a valid unified diff.")

    ensure_patch_safe(patch)
    apply_patch(patch)

    # run tests again
    if not run_tests():
        print("auto-fix: patch applied but tests still failing. Abort without committing.")
        # revert changes to avoid pushing broken code
        git("reset", "--hard")
        return 1

    # commit changes
    git("add", "-A")
    msg = "[auto-fix] fix failing tests"
    git("commit", "-m", msg)
    print("auto-fix: committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
