import argparse
import json
import re
import shutil
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

HANDLE_RE = re.compile(r"^h[0-9a-f]{8}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{12}$")
SUSPICIOUS = "hcf1d662fg9b81g432fg903eg75170de17fba"

TALENT_NAMES = {
    "All Skilled Up", "Ambidextrous", "Ancestral Knowledge", "Arrow Recovery",
    "Bigger And Better", "Comeback Kid", "Corpse Eater", "Demon",
    "Duck Duck Goose", "Dwarven Guile", "Elemental Affinity", "Elemental Ranger",
    "Escapist", "Executioner", "Far Out Man", "Five-Star Diner", "Glass Cannon",
    "Guerrilla", "Hothead", "Ice King", "Ingenious", "Leech", "Living Armour",
    "Lone Wolf", "Mnemonic", "Morning Person", "Opportunist", "Parry Master",
    "Pet Pal", "Picture of Health", "Savage Sortilege", "Slingshot",
    "Sophisticated", "Spellsong", "Stench", "Sturdy", "The Pawn", "Thrifty",
    "Torturer", "Undead", "Unstable", "Walk It Off", "What A Rush",
}

KEEP_ENGLISH_TALENTS = {"Undead"}

# Thai v1.3 already localizes most talent names. These are the talent names that
# are still English in v1.3, so the hybrid mod completes the category explicitly.
TALENT_MANUAL_OVERRIDES = {
    "Comeback Kid": "นักสู้คืนสังเวียน",
    "Elemental Ranger": "นักธนูธาตุ",
    "Glass Cannon": "พลังแรงตัวบาง",
    "Guerrilla": "กองโจร",
    "Hothead": "หัวร้อน",
    "Leech": "ปลิง",
    "Mnemonic": "ความจำเป็นเลิศ",
    "Opportunist": "นักฉวยโอกาส",
    "Pet Pal": "พูดกับสัตว์",
    "Savage Sortilege": "เวทอำมหิต",
    "Slingshot": "หนังสติ๊ก",
    "The Pawn": "เบี้ยหมาก",
}


def read_handles(path):
    vals = []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        s = raw.strip()
        if not s:
            continue
        if not HANDLE_RE.match(s):
            raise SystemExit(f"Invalid handle in {path}: {s!r}")
        vals.append(s)
    if len(vals) != len(set(vals)):
        raise SystemExit(f"Duplicate handles in {path}")
    return set(vals)

def parse_content_file(path):
    tree = ET.parse(path)
    root = tree.getroot()
    out = {}
    for e in root.iter():
        if e.tag.endswith("content") and "contentuid" in e.attrib:
            uid = e.attrib["contentuid"]
            if uid in out:
                raise SystemExit(f"Duplicate UID {uid} in {path}")
            out[uid] = e
    return tree, out

def replace_whitelisted(official_path, thai_path, out_path, whitelist):
    otree, omap = parse_content_file(official_path)
    _, tmap = parse_content_file(thai_path)
    if set(omap) != set(tmap):
        missing_th = sorted(set(omap) - set(tmap))
        missing_en = sorted(set(tmap) - set(omap))
        raise SystemExit(f"UID mismatch for {official_path.name}: missing_thai={len(missing_th)} missing_official={len(missing_en)}")
    changed = 0
    selected = 0
    for uid, oe in omap.items():
        if uid in whitelist:
            selected += 1
            te = tmap[uid]
            oe.text = te.text
            oe.tail = te.tail
            oe.attrib.clear()
            oe.attrib.update(te.attrib)
            changed += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    otree.write(out_path, encoding="utf-8", xml_declaration=True)
    return len(omap), selected, changed


def contains_thai(text):
    return any("\u0e00" <= ch <= "\u0e7f" for ch in (text or ""))

def apply_talent_policy(official_map, thai_map, out_path):
    tree, final_map = parse_content_file(out_path)
    expected = {}
    translated_from_thai = 0
    translated_manual = 0
    kept_english = 0
    unresolved = []
    matched_names = set()

    for uid, oe in official_map.items():
        name = oe.text or ""
        if name not in TALENT_NAMES:
            continue
        matched_names.add(name)
        fe = final_map[uid]

        if name in KEEP_ENGLISH_TALENTS:
            fe.text = oe.text
            fe.attrib.clear()
            fe.attrib.update(oe.attrib)
            expected[uid] = {"text": oe.text or "", "attrib": dict(oe.attrib), "name": name, "source": "official"}
            kept_english += 1
            continue

        te = thai_map[uid]
        thai_value = te.text or ""
        if contains_thai(thai_value):
            fe.text = te.text
            fe.attrib.clear()
            fe.attrib.update(te.attrib)
            expected[uid] = {"text": thai_value, "attrib": dict(te.attrib), "name": name, "source": "thai_v1.3"}
            translated_from_thai += 1
            continue

        manual = TALENT_MANUAL_OVERRIDES.get(name)
        if manual:
            fe.text = manual
            fe.attrib.clear()
            fe.attrib.update(oe.attrib)
            expected[uid] = {"text": manual, "attrib": dict(oe.attrib), "name": name, "source": "manual"}
            translated_manual += 1
        else:
            unresolved.append({"uid": uid, "name": name, "thai_value": thai_value})

    if unresolved:
        raise SystemExit(f"Unresolved English talent names: {unresolved}")

    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return expected, {
        "talent_names_matched": len(matched_names),
        "talent_entries_matched": len(expected),
        "talent_entries_from_thai_v1_3": translated_from_thai,
        "talent_entries_manual_thai": translated_manual,
        "talent_entries_kept_english": kept_english,
        "talent_keep_english_names": sorted(KEEP_ENGLISH_TALENTS),
    }

def extract_subtitle_handles(root):
    hs = set()
    files = []
    for p in root.rglob("*.lsx"):
        rel = p.relative_to(root).as_posix().lower()
        if "subtitle" not in rel:
            continue
        files.append(p)
        # Subtitle LSX resources do not use the same <content contentuid=...>
        # schema as english.xml; collect every localization handle present in
        # these dedicated subtitle files.
        txt = p.read_text(encoding="utf-8", errors="ignore")
        hs.update(re.findall(r'h[0-9a-f]{8}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{12}', txt))
    return hs, files

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", required=True)
    ap.add_argument("--thai", required=True)
    ap.add_argument("--dialogue", required=True)
    ap.add_argument("--readable", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    official = Path(args.official)
    thai = Path(args.thai)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(official, out)

    dialogue = read_handles(args.dialogue)
    readable = read_handles(args.readable)
    whitelist = dialogue | readable

    off_main = official / "Localization" / "English" / "english.xml"
    thai_main = thai / "Localization" / "English" / "english.xml"
    out_main = out / "Localization" / "English" / "english.xml"
    if not off_main.exists() or not thai_main.exists():
        raise SystemExit("english.xml not found at expected Localization/English path")

    _, omap = parse_content_file(off_main)
    _, tmap = parse_content_file(thai_main)
    if len(omap) != 92327 or len(tmap) != 92327:
        raise SystemExit(f"Unexpected main localization entry counts: official={len(omap)} thai={len(tmap)}")
    if set(omap) != set(tmap):
        raise SystemExit("Official and Thai english.xml UID sets differ")

    found_dialogue = dialogue & set(omap)
    found_readable = readable & set(omap)
    missing_dialogue = dialogue - set(omap)
    missing_readable = readable - set(omap)
    # dialogue_handles.txt is a candidate set derived from dialogue resources.
    # Some handles can legitimately be resource-local/non-localization handles.
    # The effective whitelist is therefore restricted to UIDs that exist in the
    # authoritative Official English localization table. Readable handles are
    # expected to be exact localization handles and remain fail-closed.
    if missing_readable:
        raise SystemExit(f"Readable handles missing from official localization: {len(missing_readable)}")

    effective_whitelist = whitelist & set(omap)
    suspicious_fallback = SUSPICIOUS in effective_whitelist
    if suspicious_fallback:
        # Thai v1.3 contains a known structurally suspicious/corrupted value for
        # this UID. Fail-safe behavior is to retain the authoritative Official
        # English value for this single entry instead of emitting broken XML/text.
        effective_whitelist.remove(SUSPICIOUS)

    entries, selected, changed = replace_whitelisted(off_main, thai_main, out_main, effective_whitelist)

    # Explicit UI exception requested by the player: translate the Talent
    # category completely, while keeping established gamer terms such as
    # "Undead" in English. Proper character/place names are untouched.
    talent_expected, talent_report = apply_talent_policy(omap, tmap, out_main)
    talent_uids = set(talent_expected)

    subtitle_handles, subtitle_files = extract_subtitle_handles(official)
    copied_subtitles = 0
    missing_subtitle_files = []
    for op in subtitle_files:
        rel = op.relative_to(official)
        tp = thai / rel
        dp = out / rel
        if tp.exists():
            shutil.copy2(tp, dp)
            copied_subtitles += 1
        else:
            missing_subtitle_files.append(rel.as_posix())

    # Defensive proof: non-whitelisted main localization text must remain equal to official.
    _, final_map = parse_content_file(out_main)
    mismatch_non_whitelist = []
    mismatch_whitelist = []
    mismatch_talents = []
    for uid, oe in omap.items():
        fe = final_map[uid]
        if uid in talent_uids:
            exp = talent_expected[uid]
            if (fe.text or "") != exp["text"] or fe.attrib != exp["attrib"]:
                mismatch_talents.append(uid)
        elif uid in effective_whitelist:
            te = tmap[uid]
            if (te.text or "") != (fe.text or "") or te.attrib != fe.attrib:
                mismatch_whitelist.append(uid)
        else:
            if (oe.text or "") != (fe.text or "") or oe.attrib != fe.attrib:
                mismatch_non_whitelist.append(uid)
    if mismatch_non_whitelist:
        raise SystemExit(f"Non-whitelist main localization changed: {len(mismatch_non_whitelist)}")
    if mismatch_whitelist:
        raise SystemExit(f"Whitelisted main localization did not match Thai: {len(mismatch_whitelist)}")
    if mismatch_talents:
        raise SystemExit(f"Talent localization policy mismatch: {len(mismatch_talents)}")
    if missing_subtitle_files:
        raise SystemExit(f"Thai package missing {len(missing_subtitle_files)} official subtitle files")

    report = {
        "official_main_entries": len(omap),
        "thai_main_entries": len(tmap),
        "dialogue_handles": len(dialogue),
        "readable_handles": len(readable),
        "candidate_story_whitelist": len(whitelist),
        "effective_story_whitelist": len(effective_whitelist),
        "dialogue_found": len(found_dialogue),
        "dialogue_missing_from_main_localization": len(missing_dialogue),
        "readable_found": len(found_readable),
        "readable_missing_from_main_localization": len(missing_readable),
        "subtitle_files": len(subtitle_files),
        "subtitle_files_copied_from_thai": copied_subtitles,
        "subtitle_unique_handles_observed": len(subtitle_handles),
        "main_selected_entries": selected,
        "main_non_whitelist_mismatches": len(mismatch_non_whitelist),
        "main_whitelist_mismatches": len(mismatch_whitelist),
        "talent_policy_mismatches": len(mismatch_talents),
        **talent_report,
        "suspicious_handle_selected": SUSPICIOUS in effective_whitelist,
        "suspicious_handle_fallback_to_official": suspicious_fallback,
        "suspicious_handle": SUSPICIOUS if suspicious_fallback else None,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    Path(args.report).with_name("subtitle_handles.txt").write_text("\n".join(sorted(subtitle_handles)) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
