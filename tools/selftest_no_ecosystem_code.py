#!/usr/bin/env python3
"""No ecosystem code is in this repository, and none can reach it.

    python3 tools/selftest_no_ecosystem_code.py

WHY THIS EXISTS

This repository is written to be handed to other people: a hackathon team, a
public submission, a judging panel, a GitHub repo somebody else owns. The
ecosystem repositories are not. The founder's rule, 2026-09-22, is
"Google or anyone isnt getting ecosystem code."

A promise does not enforce that. A person in a hurry copies a working module
across because it already solves the problem, and nothing objects. By the time
anyone notices, it is in somebody else's git history and cannot be recalled.

So this is the gate. It refuses, in order of how much harm it would do:

  A. A file in this repo is a copy of a file in an ecosystem repo.
  B. A file imports from an ecosystem package or module.
  C. A file reads from an ecosystem path at runtime.
  D. This repo sits INSIDE an ecosystem repo, so committing here commits there.
  E. A secret of any kind is committed.
  F. The gate itself is pointed at nothing, and passes by vacuum.

F is the one that matters most and is easiest to get wrong. If the ecosystem
directories are missing, renamed, or unreadable, every "no copy found" check
passes trivially and the gate reports GREEN while proving nothing. That is the
exact shape this project calls a reading that cannot come out differently. So
the gate asserts FIRST that it can actually see the thing it is searching, and
goes RED if it cannot.
"""
import hashlib
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent
HOME = pathlib.Path.home()

# The repositories whose code must never appear here.
ECOSYSTEM = [
    HOME / "Documents" / "MentalGym_Project",
    HOME / "Documents" / "SovereignHub",
    HOME / "Documents" / "zealousmirror-app",
]

# Import roots that only exist inside the ecosystem.
ECOSYSTEM_MODULES = {
    "sovereign_secrets", "sovereign_session", "sovereign_enhance", "sovereign_loop",
    "outbound_lock", "outward_loads", "log_hygiene", "notifications", "hermes_bridge",
    "formation_truth", "source_class", "runtime_probe", "logtail", "space_reaper",
    "disk_guard", "pricing", "affiliates", "auth", "db", "cloudflare_edge",
    "verify_integrations", "text_assert", "immune", "nexus", "morum",
}

# Substrings that would mean this code reaches back into the ecosystem at runtime.
ECOSYSTEM_PATHS = [
    "MentalGym_Project", "SovereignHub", "zealousmirror-app",
    ".morum", "morum_", "ZM_PlayerData", "ZM_VGIAudit", "sovereign_",
]

SECRET = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|sk_live_[A-Za-z0-9]{10,}|rk_live_[A-Za-z0-9]{10,}|whsec_[A-Za-z0-9]{20,}"
    r"|://[^/\s:]+:[^/\s@]{4,}@)"
)

TEXT_SUFFIXES = {".py", ".lua", ".sh", ".js", ".ts", ".html", ".css", ".md",
                 ".json", ".yml", ".yaml", ".txt", ".toml", ".cfg"}

FAILS = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + (("  -- " + detail) if (detail and not ok) else ""))
    if not ok:
        FAILS.append(name)


def own_files():
    """Every file this repository would hand to somebody else."""
    out = []
    for p in HERE.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(HERE)
        parts = set(rel.parts)
        if parts & {".git", "__pycache__", ".venv", "node_modules", "logs"}:
            continue
        # THE GATE DOES NOT JUDGE ITSELF.
        #
        # This file is deployed into every clean room from one canonical copy
        # that lives inside the ecosystem, so it is byte-identical to an
        # ecosystem file on purpose. Without this line it reports itself as a
        # copied ecosystem file and every new project is born red.
        #
        # This is the only exemption and it is narrow: one exact filename,
        # never a directory and never a pattern. Its integrity is not taken on
        # trust either -- CLEANROOM.sha256 records the canonical hash and
        # `new_clean_room.py --check` compares the deployed copy against it,
        # because a quietly weakened gate is how a breach ships.
        if p.resolve() == pathlib.Path(__file__).resolve():
            continue
        out.append(p)
    return out


def digest(path):
    """Hash of the file with whitespace-only differences ignored.

    A copy that has been reindented or had its line endings changed is still a
    copy. Hashing the raw bytes would miss exactly the copy somebody made by
    pasting into an editor.
    """
    try:
        raw = path.read_bytes()
    except Exception:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return hashlib.sha256(raw).hexdigest()
    norm = re.sub(r"\s+", " ", text).strip()
    if len(norm) < 200:          # too short to be a meaningful copy
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# ── the ecosystem digest cache ─────────────────────────────────────────────
#
# Hashing 36,746 ecosystem files takes 38.5 seconds, measured 2026-10-04. A
# gate that slow does not get run, and CLAUDE.md already records the lesson
# that a selftest nobody runs is a comment. With open source projects and
# competitions ongoing, this gate runs constantly or it runs never.
#
# So the digests are cached, keyed on a fingerprint of the ecosystem's SHAPE:
# every file's path, size and modification time. Cheap to build because it
# stats rather than reads. If ANY tracked file is added, removed, resized or
# touched, the fingerprint changes and everything is rehashed. A cache that
# could survive a change to what it summarises would be worse than no cache,
# because the gate would pass against an ecosystem that no longer exists.
#
# The cache lives outside every repository. Inside a public project it would
# be shipped, and inside the ecosystem it would be a file the gate then has to
# reason about.
CACHE_DIR = pathlib.Path.home() / ".cache" / "zm_cleanroom"


def _eco_fingerprint(files):
    h = hashlib.sha256()
    for p in sorted(files):
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(("%s|%d|%d\n" % (p, st.st_size, st.st_mtime_ns)).encode())
    return h.hexdigest()


def _eco_digests_cached(eco_files):
    """{digest: path} for the ecosystem, rehashed only when it has changed."""
    fp = _eco_fingerprint(eco_files)
    cache = CACHE_DIR / ("%s.json" % fp)
    if cache.is_file():
        try:
            d = json.loads(cache.read_text())
            if isinstance(d, dict) and d:
                return {k: pathlib.Path(v) for k, v in d.items()}
        except Exception:
            pass
    out = {}
    for p in eco_files:
        d = digest(p)
        if d:
            out.setdefault(d, p)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # one fingerprint, one file. A stale cache is never read because its
        # name can no longer be computed from the ecosystem as it stands.
        for old in CACHE_DIR.glob("*.json"):
            old.unlink()
        cache.write_text(json.dumps({k: str(v) for k, v in out.items()}))
    except OSError:
        pass
    return out


def main() -> int:
    print()
    print("  NO ECOSYSTEM CODE")
    print("  " + "-" * 62)

    mine = own_files()

    # ── F · the gate can see what it is searching ───────────────────────────
    # Checked FIRST. Everything below is meaningless if this is false.
    visible = [r for r in ECOSYSTEM if r.is_dir()]
    check("F PLANTED the gate can actually see the ecosystem repos",
          len(visible) == len(ECOSYSTEM),
          "missing: %s" % [str(r) for r in ECOSYSTEM if not r.is_dir()])

    eco_files = []
    for root in visible:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            # NOT ECOSYSTEM SOURCE, and so not a breach to match against.
            #
            # Measured 2026-10-04: 20,314 of 36,747 scanned files, 55%, were
            # vendor or archive. node_modules and dist are third-party or built
            # output, and a public project copying from node_modules has copied
            # a public npm package, not our work. _archive and backups are dead
            # duplicates of files that are still checked in their live form.
            # logs are runtime state.
            #
            # Dropping them makes the gate both faster and more correct: every
            # match it reports now points at real ecosystem source.
            if set(p.parts) & {".git", "__pycache__", "node_modules",
                               "_archive", "backups", "dist", "logs",
                               ".venv", "build"}:
                continue
            if p.suffix.lower() in TEXT_SUFFIXES:
                eco_files.append(p)
    check("F and it read a substantial number of ecosystem files",
          len(eco_files) > 200, "only read %d" % len(eco_files))
    check("F and it has files of its own to judge", len(mine) > 0,
          "this repo appears empty")

    # ── D · this repo is not nested inside an ecosystem repo ────────────────
    inside = [str(r) for r in ECOSYSTEM if r in HERE.parents or r == HERE]
    check("D PLANTED this repo is not inside an ecosystem repo",
          not inside, "nested under: %s" % inside)

    # ── A · no file here is a copy of a file there ──────────────────────────
    eco_digests = _eco_digests_cached(eco_files)
    copies = []
    for p in mine:
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        d = digest(p)
        if d and d in eco_digests:
            copies.append("%s == %s" % (p.relative_to(HERE), eco_digests[d]))
    check("A PLANTED no file here is a copy of an ecosystem file",
          not copies, "; ".join(copies[:3]))

    # ── B · no file imports an ecosystem module ─────────────────────────────
    bad_imports = []
    for p in mine:
        if p.suffix != ".py":
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", src, re.M):
            root = m.group(1).split(".")[0]
            if root in ECOSYSTEM_MODULES:
                bad_imports.append("%s imports %s" % (p.relative_to(HERE), m.group(1)))
    check("B PLANTED no file imports an ecosystem module",
          not bad_imports, "; ".join(bad_imports[:3]))

    # ── C · no file reaches an ecosystem path at runtime ────────────────────
    # This file names those paths on purpose, so it exempts itself by identity
    # rather than by a pattern that would also exempt a real offender.
    self_path = pathlib.Path(__file__).resolve()
    reaches = []
    for p in mine:
        if p.resolve() == self_path or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except Exception:
            continue
        code = "\n".join(re.sub(r"(#|//|--).*$", "", ln) for ln in src.splitlines())
        for token in ECOSYSTEM_PATHS:
            if token in code:
                reaches.append("%s mentions %s" % (p.relative_to(HERE), token))
                break
    check("C PLANTED no file reaches into an ecosystem path",
          not reaches, "; ".join(reaches[:3]))

    # ── E · nothing secret is committed ─────────────────────────────────────
    leaked = []
    for p in mine:
        if p.resolve() == self_path or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if SECRET.search(src):
            leaked.append(str(p.relative_to(HERE)))
    check("E PLANTED no secret is committed", not leaked, ", ".join(leaked[:3]))

    print()
    if FAILS:
        print("  no-ecosystem-code gate RED - %d failing\n" % len(FAILS))
        return 1
    print("  no-ecosystem-code gate GREEN - %d files here, checked against %d there\n"
          % (len(mine), len(eco_files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
