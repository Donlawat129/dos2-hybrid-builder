import argparse
import hashlib
import json
from pathlib import Path

def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def inventory(root):
    root = Path(root)
    return {
        p.relative_to(root).as_posix(): sha256(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", required=True)
    ap.add_argument("--roundtrip", required=True)
    ap.add_argument("--merge-report", required=True)
    ap.add_argument("--pak", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    staged = inventory(args.staged)
    rt = inventory(args.roundtrip)
    missing = sorted(set(staged) - set(rt))
    extra = sorted(set(rt) - set(staged))
    changed = sorted(k for k in set(staged) & set(rt) if staged[k] != rt[k])

    merge = json.loads(Path(args.merge_report).read_text(encoding="utf-8"))
    pak = Path(args.pak)

    result = {
        "status": "PASS" if not missing and not extra and not changed else "FAIL",
        "staged_file_count": len(staged),
        "roundtrip_file_count": len(rt),
        "missing_after_roundtrip": missing,
        "extra_after_roundtrip": extra,
        "changed_after_roundtrip": changed,
        "pak_size_bytes": pak.stat().st_size,
        "pak_sha256": sha256(pak),
        "merge": merge,
    }

    Path(args.out_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    md = [
        "# DOS2 Hybrid Build QA",
        "",
        f"**Status:** {result['status']}",
        "",
        f"- Staged files: {len(staged)}",
        f"- Round-trip files: {len(rt)}",
        f"- Missing after round-trip: {len(missing)}",
        f"- Extra after round-trip: {len(extra)}",
        f"- Changed after round-trip: {len(changed)}",
        f"- English.pak size: {pak.stat().st_size} bytes",
        f"- English.pak SHA-256: `{result['pak_sha256']}`",
        "",
        "## Localization merge",
        "",
    ]
    for k, v in merge.items():
        md.append(f"- {k}: {v}")
    if missing or extra or changed:
        md += ["", "## Round-trip mismatches", ""]
        for label, values in (("Missing", missing), ("Extra", extra), ("Changed", changed)):
            if values:
                md.append(f"### {label}")
                md.extend(f"- `{x}`" for x in values[:100])
    Path(args.out_md).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit("Round-trip QA failed")

if __name__ == "__main__":
    main()
