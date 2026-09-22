import argparse
import json
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

HANDLE_RE = re.compile(r"^h[0-9a-f]{8}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{12}$")
HANDLE_ANY_RE = re.compile(r"h[0-9a-f]{8}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{4}g[0-9a-f]{12}")
SUSPICIOUS = "hcf1d662fg9b81g432fg903eg75170de17fba"

ATTRIBUTE_NAMES = {
    "Strength", "Finesse", "Intelligence", "Constitution", "Memory", "Wits",
}

COMBAT_ABILITY_NAMES = {
    "Single-Handed", "Two-Handed", "Ranged", "Dual Wielding",
    "Warfare", "Huntsman", "Scoundrel", "Pyrokinetic", "Hydrosophist",
    "Aerotheurge", "Geomancer", "Necromancer", "Summoning", "Polymorph",
    "Retribution", "Leadership", "Perseverance",
}

# Exact standalone game/proper terms that should remain searchable and recognizable.
KEEP_ENGLISH_EXACT = {
    "Fane", "Red Prince", "The Red Prince", "Lohse", "Sebille",
    "Ifan ben-Mezd", "Beast", "Fort Joy", "Source", "Undead",
}

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

KNOWN_COMBAT_SKILLS = {"Mosquito Swarm", "Battering Ram", "Battle Stomp", "Fortify", "Restoration"}

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

def contains_thai(text):
    return any("\u0e00" <= ch <= "\u0e7f" for ch in (text or ""))

def load_skill_handles(config_dir):
    handles = set()
    files = sorted(Path(config_dir).glob("protected_skill_handles_*.txt"))
    if not files:
        raise SystemExit("No protected_skill_handles_*.txt config files found")
    for p in files:
        for raw in p.read_text(encoding="utf-8-sig").splitlines():
            s = raw.strip()
            if not s:
                continue
            if not HANDLE_RE.fullmatch(s):
                raise SystemExit(f"Invalid protected skill handle in {p}: {s!r}")
            handles.add(s)
    return handles, files

def replace_entry(dst, src):
    dst.text = src.text
    dst.tail = src.tail
    dst.attrib.clear()
    dst.attrib.update(src.attrib)

def extract_subtitle_handles(root):
    hs = set()
    files = []
    for p in root.rglob("*.lsx"):
        rel = p.relative_to(root).as_posix().lower()
        if "subtitle" not in rel:
            continue
        files.append(p)
        txt = p.read_text(encoding="utf-8", errors="ignore")
        hs.update(HANDLE_ANY_RE.findall(txt))
    return hs, files

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", required=True)
    ap.add_argument("--thai", required=True)
    ap.add_argument("--skill-handles-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    official = Path(args.official)
    thai = Path(args.thai)
    out = Path(args.out)

    # v2 policy: Thai v1.3 is the package baseline. English is restored only for
    # protected gameplay terminology/categories.
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(thai, out)

    off_main = official / "Localization" / "English" / "english.xml"
    thai_main = thai / "Localization" / "English" / "english.xml"
    out_main = out / "Localization" / "English" / "english.xml"

    otree, omap = parse_content_file(off_main)
    _, tmap = parse_content_file(thai_main)
    final_tree, fmap = parse_content_file(out_main)

    if len(omap) != 92327 or len(tmap) != 92327 or len(fmap) != 92327:
        raise SystemExit(
            f"Unexpected entry counts official={len(omap)} thai={len(tmap)} final={len(fmap)}"
        )
    if set(omap) != set(tmap) or set(omap) != set(fmap):
        raise SystemExit("Official/Thai/final UID sets differ")

    skill_candidates, skill_files = load_skill_handles(args.skill_handles_dir)
    skill_effective = skill_candidates & set(omap)
    skill_missing = skill_candidates - set(omap)

    # Resource tables can reference one localization UID while another UID
    # carries the same exact Official skill label/description in a different UI
    # surface. Protect all exact-text aliases so duplicated skill strings stay
    # English everywhere.
    skill_resource_texts = {
        (omap[uid].text or "") for uid in skill_effective if (omap[uid].text or "")
    }
    skill_text_alias_uids = {
        uid for uid, e in omap.items() if (e.text or "") in skill_resource_texts
    }
    skill_protected_uids = skill_effective | skill_text_alias_uids

    protected_name_uids = {
        uid for uid, e in omap.items()
        if (e.text or "") in (ATTRIBUTE_NAMES | COMBAT_ABILITY_NAMES | KEEP_ENGLISH_EXACT)
    }

    talent_expected = {}
    talent_manual = 0
    talent_from_thai = 0
    talent_kept_english = 0
    talent_unresolved = []

    # First restore the exact protected English categories.
    english_protected_uids = set(skill_protected_uids) | protected_name_uids | {SUSPICIOUS}
    for uid in english_protected_uids:
        replace_entry(fmap[uid], omap[uid])

    # Talent category is Thai, except established gamer term "Undead".
    for uid, oe in omap.items():
        name = oe.text or ""
        if name not in TALENT_NAMES:
            continue

        fe = fmap[uid]
        te = tmap[uid]

        if name in KEEP_ENGLISH_TALENTS:
            replace_entry(fe, oe)
            talent_expected[uid] = ("official", oe.text or "", dict(oe.attrib))
            talent_kept_english += 1
        elif contains_thai(te.text or ""):
            replace_entry(fe, te)
            talent_expected[uid] = ("thai_v1.3", te.text or "", dict(te.attrib))
            talent_from_thai += 1
        elif name in TALENT_MANUAL_OVERRIDES:
            fe.text = TALENT_MANUAL_OVERRIDES[name]
            fe.tail = oe.tail
            fe.attrib.clear()
            fe.attrib.update(oe.attrib)
            talent_expected[uid] = ("manual", fe.text or "", dict(fe.attrib))
            talent_manual += 1
        else:
            talent_unresolved.append({"uid": uid, "name": name, "thai_value": te.text or ""})

    if talent_unresolved:
        raise SystemExit(f"Unresolved Talent translations: {talent_unresolved}")

    final_tree.write(out_main, encoding="utf-8", xml_declaration=True)

    # Reparse after all mutations for QA.
    _, final_map = parse_content_file(out_main)

    # Known combat skill guard: every known skill present in Official must be
    # included in the resource-derived skill protection set and remain English.
    known_skill_check = {}
    for name in sorted(KNOWN_COMBAT_SKILLS):
        uids = [uid for uid, e in omap.items() if (e.text or "") == name]
        if not uids:
            known_skill_check[name] = {"uids": [], "protected": False, "status": "not_found"}
            continue
        protected = all(uid in skill_protected_uids for uid in uids)
        english_final = all((final_map[uid].text or "") == name for uid in uids)
        known_skill_check[name] = {
            "uids": uids,
            "protected": protected,
            "english_final": english_final,
            "status": "pass" if protected and english_final else "fail",
        }
        if not protected or not english_final:
            raise SystemExit(f"Combat skill protection failed for {name}: {known_skill_check[name]}")

    # Main localization QA: protected entries must equal Official; manual Talent
    # entries must equal explicit translations; every other entry must equal Thai.
    protected_mismatches = []
    thai_baseline_mismatches = []
    talent_mismatches = []

    manual_talent_uids = set(talent_expected)
    final_english_protected = english_protected_uids | {
        uid for uid, (source, _, _) in talent_expected.items() if source == "official"
    }

    for uid, fe in final_map.items():
        if uid in manual_talent_uids:
            source, expected_text, expected_attr = talent_expected[uid]
            if (fe.text or "") != expected_text or fe.attrib != expected_attr:
                talent_mismatches.append(uid)
        elif uid in final_english_protected:
            oe = omap[uid]
            if (fe.text or "") != (oe.text or "") or fe.attrib != oe.attrib:
                protected_mismatches.append(uid)
        else:
            te = tmap[uid]
            if (fe.text or "") != (te.text or "") or fe.attrib != te.attrib:
                thai_baseline_mismatches.append(uid)

    if protected_mismatches:
        raise SystemExit(f"English protected entries mismatch: {len(protected_mismatches)}")
    if thai_baseline_mismatches:
        raise SystemExit(f"Thai baseline entries mismatch: {len(thai_baseline_mismatches)}")
    if talent_mismatches:
        raise SystemExit(f"Talent policy entries mismatch: {len(talent_mismatches)}")

    # Thai baseline must retain complete cinematic subtitle coverage.
    off_sub_handles, off_sub_files = extract_subtitle_handles(official)
    th_sub_handles, th_sub_files = extract_subtitle_handles(thai)
    out_sub_handles, out_sub_files = extract_subtitle_handles(out)

    off_rel = {p.relative_to(official).as_posix() for p in off_sub_files}
    th_rel = {p.relative_to(thai).as_posix() for p in th_sub_files}
    out_rel = {p.relative_to(out).as_posix() for p in out_sub_files}
    if off_rel != th_rel or th_rel != out_rel:
        raise SystemExit(
            f"Subtitle file set mismatch official={len(off_rel)} thai={len(th_rel)} final={len(out_rel)}"
        )

    report = {
        "policy_version": "v2-thai-baseline-english-gameplay-protection",
        "official_main_entries": len(omap),
        "thai_main_entries": len(tmap),
        "final_main_entries": len(final_map),
        "skill_protection_config_files": len(skill_files),
        "skill_protection_candidate_handles": len(skill_candidates),
        "skill_protection_effective_handles": len(skill_effective),
        "skill_protection_text_alias_uids": len(skill_text_alias_uids),
        "skill_protection_total_uids": len(skill_protected_uids),
        "skill_protection_missing_from_main": len(skill_missing),
        "attribute_names_protected": sorted(ATTRIBUTE_NAMES),
        "combat_ability_names_protected": sorted(COMBAT_ABILITY_NAMES),
        "protected_exact_terms": sorted(KEEP_ENGLISH_EXACT),
        "protected_name_uid_count": len(protected_name_uids),
        "english_protected_uid_count": len(final_english_protected),
        "known_combat_skill_check": known_skill_check,
        "talent_entries_from_thai_v1_3": talent_from_thai,
        "talent_entries_manual_thai": talent_manual,
        "talent_entries_kept_english": talent_kept_english,
        "talent_keep_english_names": sorted(KEEP_ENGLISH_TALENTS),
        "suspicious_handle_fallback_to_official": True,
        "suspicious_handle": SUSPICIOUS,
        "protected_mismatches": len(protected_mismatches),
        "thai_baseline_mismatches": len(thai_baseline_mismatches),
        "talent_policy_mismatches": len(talent_mismatches),
        "subtitle_files": len(out_rel),
        "subtitle_unique_handles_official": len(off_sub_handles),
        "subtitle_unique_handles_thai": len(th_sub_handles),
        "subtitle_unique_handles_final": len(out_sub_handles),
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.report).with_name("protected_skill_handles_effective.txt").write_text(
        "\n".join(sorted(skill_protected_uids)) + "\n", encoding="utf-8"
    )
    Path(args.report).with_name("subtitle_handles.txt").write_text(
        "\n".join(sorted(out_sub_handles)) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))

if __name__ == "__main__":
    main()
