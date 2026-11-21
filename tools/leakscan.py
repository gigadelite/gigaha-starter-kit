#!/usr/bin/env python3
"""Fail if anything personal from the source household leaks into the kit.

Checks every tracked text file (and anything under out/ if present) for:
  - tokens whose hash is in tools/leak_hashes.txt (names, domains, device names; the
    words themselves are never stored in this repo)
  - private IPv4 addresses outside the documentation placeholders
  - email addresses, and strings that look like tokens or JWTs
Usage: python3 tools/leakscan.py [paths...]   (default: the repo + out/)
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASHES = {l.strip() for l in (ROOT / "tools/leak_hashes.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
SKIP_DIRS = {".git", "__pycache__", "node_modules"}
SKIP_FILES = {"leak_hashes.txt"}
TEXT_EXT = {".py", ".yaml", ".yml", ".md", ".txt", ".json", ".j2", ".js", ".jinja", ".sh", ".css", ".html", ""}
TOKEN_SPLITS = [re.compile(r"[a-z0-9_.]+"), re.compile(r"[a-z0-9_]+"), re.compile(r"[a-z0-9]+")]
IP = re.compile(r"\b(10|172|192)\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
SECRET = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}|\b(ghp|gho|github_pat)_[A-Za-z0-9_]{20,}")
ALLOWED_EMAIL = ("noreply@anthropic.com",)


def h(tok: str) -> str:
    return hashlib.sha256(tok.encode()).hexdigest()[:16]


def scan_file(path: Path) -> list[str]:
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        toks = set()
        for rx in TOKEN_SPLITS:
            toks.update(rx.findall(low))
        # also every prefix of dotted/underscored tokens (so a banned subnet prefix matches any full address in it)
        for t in list(toks):
            parts = re.split(r"([._])", t)
            for i in range(1, len(parts), 2):
                toks.add("".join(parts[:i]))
        bad = [t for t in toks if h(t) in HASHES]
        if bad:
            hits.append(f"{path.relative_to(ROOT)}:{n}: personal token (hash {h(bad[0])})")
        for m in IP.finditer(line):
            a, b = int(m[2]), int(m[3])
            private = m[1] == "10" or (m[1] == "172" and 16 <= a <= 31) or (m[1] == "192" and a == 168)
            if private and not (m[1] == "192" and a == 168 and b == 1):  # 192.168.1.x reserved for examples
                hits.append(f"{path.relative_to(ROOT)}:{n}: private IP {m[0]}")
        for m in EMAIL.finditer(line):
            if m[0] not in ALLOWED_EMAIL and not m[0].endswith(("@example.com", ".invalid")):
                hits.append(f"{path.relative_to(ROOT)}:{n}: email {m[0]}")
        if SECRET.search(line):
            hits.append(f"{path.relative_to(ROOT)}:{n}: looks like a token")
    return hits


def main(argv: list[str]) -> int:
    roots = [Path(a).resolve() for a in argv] or [ROOT]
    hits = []
    for r in roots:
        files = [r] if r.is_file() else [p for p in r.rglob("*") if p.is_file()]
        for p in files:
            if SKIP_DIRS & set(p.parts) or p.name in SKIP_FILES or p.suffix not in TEXT_EXT:
                continue
            hits += scan_file(p)
    for x in hits:
        print(x)
    print(f"leakscan: {'FAIL, ' + str(len(hits)) + ' hit(s)' if hits else 'clean'}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
