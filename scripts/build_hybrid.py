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

CIVIL_ABILITY_NAMES = {
    "Bartering", "Persuasion", "Lucky Charm", "Loremaster",
    "Telekinesis", "Sneaking", "Thievery",
}

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

# Item-tooltip-specific handles. These intentionally override English protection
# because the same English terms can also exist in Attribute/Skill contexts.
ITEM_THAI_OVERRIDES = {
    "h823595e6g550fg4614gb1ddgdcd323bb4c69": "(ว่าง)",
    "hd9f9cf80g7affg4a45g8519gd705ed9bc3bd": "เกราะเวท",
    "h39c85003g58bdg48a5g95f0ge4f5a9f4e3b0": "พลังชีวิต",
    "hb5c52d20g6855g4929ga78ege3fe776a1f2e": "เกราะอก",
    "h77557ac7g4f6fg49bdga76cg404de43d92f5": "โล่",
    "h970199f8ge650g4fa3ga0deg5995696569b6": "แหวน",
    "h2a76a9ecg2982g4c7bgb66fgbe707db0ac9e": "เข็มขัด",
    "h185545eagdaf0g4286ga411gd50cbdcabc8b": "ถุงมือ",
    "hdede3a7dgf545g4352g8b89gb21a43825649": "ได้รับแท็ก:",
    "h04e506dbg478ag4160gb770g8da9786ff4b8": "แต้มแอ็กชันสูงสุด",
    "h54bec796ge442g4d5fgb6bbg524e36927eac": "แต้มแอ็กชันเริ่มต้น:",
    "hdf87671fg549ag4025g8f28gb132b9ca9fe4": "แต้มแอ็กชันต่อรอบ",
}

KNOWN_COMBAT_SKILLS = {
    "Mosquito Swarm", "Battering Ram", "Battle Stomp", "Fortify",
    "Restoration", "Raise Bloated Corpse",
}

SCREENSHOT_ATTRIBUTE_GUARDS = {
    "hc8c67074g3c19g44d1g8b7bg9e5a8d06d87f": "Strength",
    "h9531fd22g6366g4e93g9b08g11763cac0d86": "Damage",
    "hb677b3f7g5cf6g49c3g84fag2f773ef50dd6": "Physical Armour",
    "hc6dcb940gb6b6g41aagaeceg31008af9c082": "Magic Armour",
    "h051b2501g091ag4c93ga699g407cd2b29cdc": "Fire",
    "hd30196cdg0253g434dga42ag12be43dac4ec": "Water",
    "h85fee3f4g0226g41c6g9d38g83b7b5bf96ba": "Earth",
    "h1cea7e28gc8f1g4915ga268g31f90767522c": "Air",
    "haa64cdb8g22d6g40d6g9918g61961514f70f": "Poison",
    "h18f97d5bg9a79g4917g809dgb0ac7a5ec302": None,
}

SCREENSHOT_CIVIL_GUARDS = {
    "hcc404653ga10ag4f56g8119g11162e60f81d": "Bartering",
    "h257372d3g6f98g4450g813bg190e19aecce4": "Persuasion",
    "h2f9ec5acgbcbeg45b8g8058gee363e6875d5": "Lucky Charm",
    "hb8aa942egbeaag4452gbfbcg31b493bead6e": "Loremaster",
    "h455eb073g28abg4f3bgae9dga8a592a30cdb": "Telekinesis",
    "h1633e511g35e3g4e22gb999gbbf3b0d5ce5e": "Thievery",
    "h6bf7caf0g7756g443bg926dg1ee5975ee133": "Sneaking",
}

SCREENSHOT_SKILL_GUARDS = {
    "habb90745gdd7bg4eebg8c22g5bd99e5dc3ab": "Raise Bloated Corpse",
    "h2da15bf3g40fag4c1agbfddg6fb4e6c2a8f7": None,
    "h3434ef83g57cbg4b4fga736g3f0b4f7a037f": None,
}


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


def read_handle_files(files):
    handles = set()
    loaded = []
    for p in files:
        p = Path(p)
        if not p.exists():
            continue
        loaded.append(p)
        for raw in p.read_text(encoding="utf-8-sig").splitlines():
            value = raw.strip()
            if not value:
                continue
            if not HANDLE_RE.fullmatch(value):
                raise SystemExit(f"Invalid handle in {p}: {value!r}")
            handles.add(value)
    return handles, loaded


def load_exact_handle_file(config_dir, name):
    p = Path(config_dir) / name
    handles, files = read_handle_files([p])
    if not files:
        raise SystemExit(f"Required config missing: {p}")
    return handles


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


def assert_same_entry(uid, actual, expected, label):
    if (actual.text or "") != (expected.text or "") or actual.attrib != expected.attrib:
        raise SystemExit(
            f"{label} mismatch for {uid}: final={actual.text!r} expected={expected.text!r}"
        )


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
    config_dir = Path(args.skill_handles_dir)
    out = Path(args.out)

    # v3: Thai v1.3 baseline, with context-specific English protection.
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(thai, out)

    off_main = official / "Localization" / "English" / "english.xml"
    thai_main = thai / "Localization" / "English" / "english.xml"
    out_main = out / "Localization" / "English" / "english.xml"

    _, omap = parse_content_file(off_main)
    _, tmap = parse_content_file(thai_main)
    final_tree, fmap = parse_content_file(out_main)

    if len(omap) != 92327 or len(tmap) != 92327 or len(fmap) != 92327:
        raise SystemExit(
            f"Unexpected entry counts official={len(omap)} thai={len(tmap)} final={len(fmap)}"
        )
    if set(omap) != set(tmap) or set(omap) != set(fmap):
        raise SystemExit("Official/Thai/final UID sets differ")

    # Core combat-skill localization resources. Do NOT expand by text aliases:
    # generic strings such as Magic Armour are shared with item tooltips.
    core_skill_files = []
    for i in range(1, 8):
        core_skill_files.append(config_dir / f"protected_skill_handles_{i:02d}.txt")
    core_skill_handles, core_skill_loaded = read_handle_files(core_skill_files)

    status_files = sorted(config_dir.glob("protected_skill_handles_status_*.txt"))
    status_handles, status_loaded = read_handle_files(status_files)
    manual_skill_handles = load_exact_handle_file(config_dir, "protected_skill_handles_manual.txt")
    attribute_handles = load_exact_handle_file(config_dir, "protected_attribute_handles.txt")
    ability_handles = load_exact_handle_file(config_dir, "protected_ability_handles.txt")

    all_uids = set(omap)
    skill_candidates = core_skill_handles | status_handles | manual_skill_handles
    skill_protected = skill_candidates & all_uids
    skill_missing = skill_candidates - all_uids

    attribute_protected = attribute_handles & all_uids
    attribute_missing = attribute_handles - all_uids
    ability_protected = ability_handles & all_uids
    ability_missing = ability_handles - all_uids

    if attribute_missing:
        raise SystemExit(f"Attribute config handles missing from Official localization: {len(attribute_missing)}")
    if ability_missing:
        raise SystemExit(f"Ability config handles missing from Official localization: {len(ability_missing)}")

    # Names that should remain English wherever referenced as gameplay terms.
    protected_texts = ATTRIBUTE_NAMES | COMBAT_ABILITY_NAMES | CIVIL_ABILITY_NAMES | KEEP_ENGLISH_EXACT
    protected_text_uids = {
        uid for uid, e in omap.items() if (e.text or "") in protected_texts
    }

    english_protected_uids = (
        skill_protected
        | attribute_protected
        | ability_protected
        | protected_text_uids
        | {SUSPICIOUS}
    )

    for uid in english_protected_uids:
        replace_entry(fmap[uid], omap[uid])

    # Talent category remains Thai, except Undead.
    talent_expected = {}
    talent_from_thai = 0
    talent_manual = 0
    talent_kept_english = 0
    unresolved_talents = []

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
            unresolved_talents.append({"uid": uid, "name": name, "thai_value": te.text or ""})

    if unresolved_talents:
        raise SystemExit(f"Unresolved Talent translations: {unresolved_talents}")

    # Item-tooltip-specific Thai cleanup. This runs after English protection by
    # design, because item contexts must stay Thai even when the same term is
    # English on the Character Sheet.
    for uid, value in ITEM_THAI_OVERRIDES.items():
        if uid not in fmap:
            raise SystemExit(f"Item override UID not found: {uid}")
        fmap[uid].text = value

    # Known corrupt Thai entry always falls back to Official last.
    replace_entry(fmap[SUSPICIOUS], omap[SUSPICIOUS])

    final_tree.write(out_main, encoding="utf-8", xml_declaration=True)
    _, final_map = parse_content_file(out_main)

    # Screenshot/acceptance guards.
    for uid, expected_text in SCREENSHOT_ATTRIBUTE_GUARDS.items():
        assert_same_entry(uid, final_map[uid], omap[uid], "Attribute")
        if expected_text is not None and (final_map[uid].text or "") != expected_text:
            raise SystemExit(f"Attribute text guard failed for {uid}")

    for uid, expected_text in SCREENSHOT_CIVIL_GUARDS.items():
        assert_same_entry(uid, final_map[uid], omap[uid], "Civil ability")
        if expected_text is not None and (final_map[uid].text or "") != expected_text:
            raise SystemExit(f"Civil ability text guard failed for {uid}")

    for uid, expected_text in SCREENSHOT_SKILL_GUARDS.items():
        assert_same_entry(uid, final_map[uid], omap[uid], "Combat skill")
        if expected_text is not None and (final_map[uid].text or "") != expected_text:
            raise SystemExit(f"Combat skill text guard failed for {uid}")

    for uid, value in ITEM_THAI_OVERRIDES.items():
        if (final_map[uid].text or "") != value:
            raise SystemExit(f"Item Thai override failed for {uid}: {final_map[uid].text!r}")

    known_skill_check = {}
    for name in sorted(KNOWN_COMBAT_SKILLS):
        uids = [uid for uid, e in omap.items() if (e.text or "") == name]
        if not uids:
            known_skill_check[name] = {"uids": [], "english_final": False, "status": "not_found"}
            continue
        english_final = all((final_map[uid].text or "") == name for uid in uids)
        known_skill_check[name] = {
            "uids": uids,
            "english_final": english_final,
            "status": "pass" if english_final else "fail",
        }
        if not english_final:
            raise SystemExit(f"Combat skill name guard failed for {name}: {uids}")

    # Precedence-aware QA.
    item_override_uids = set(ITEM_THAI_OVERRIDES)
    talent_uids = set(talent_expected)
    english_final_uids = (
        english_protected_uids
        | {uid for uid, (source, _, _) in talent_expected.items() if source == "official"}
    ) - item_override_uids - {
        uid for uid, (source, _, _) in talent_expected.items() if source != "official"
    }

    protected_mismatches = []
    thai_baseline_mismatches = []
    talent_mismatches = []
    item_override_mismatches = []

    for uid, fe in final_map.items():
        if uid in item_override_uids:
            if (fe.text or "") != ITEM_THAI_OVERRIDES[uid]:
                item_override_mismatches.append(uid)
        elif uid in talent_uids:
            source, expected_text, expected_attr = talent_expected[uid]
            if (fe.text or "") != expected_text or fe.attrib != expected_attr:
                talent_mismatches.append(uid)
        elif uid in english_final_uids:
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
    if item_override_mismatches:
        raise SystemExit(f"Item Thai override mismatches: {len(item_override_mismatches)}")

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
        "policy_version": "v3-context-specific-ui",
        "official_main_entries": len(omap),
        "thai_main_entries": len(tmap),
        "final_main_entries": len(final_map),
        "core_skill_config_files": len(core_skill_loaded),
        "status_skill_config_files": len(status_loaded),
        "skill_protection_candidate_handles": len(skill_candidates),
        "skill_protection_effective_handles": len(skill_protected),
        "skill_protection_missing_from_main": len(skill_missing),
        "attribute_protection_handles": len(attribute_protected),
        "attribute_protection_missing": len(attribute_missing),
        "ability_protection_handles": len(ability_protected),
        "ability_protection_missing": len(ability_missing),
        "protected_text_uid_count": len(protected_text_uids),
        "english_protected_uid_count": len(english_final_uids),
        "item_thai_override_count": len(ITEM_THAI_OVERRIDES),
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
        "item_override_mismatches": len(item_override_mismatches),
        "subtitle_files": len(out_rel),
        "subtitle_unique_handles_official": len(off_sub_handles),
        "subtitle_unique_handles_thai": len(th_sub_handles),
        "subtitle_unique_handles_final": len(out_sub_handles),
        "shared_tooltip_language_note": (
            "Generic tooltip chrome such as Requires/Range/Level remains Thai because "
            "the same localization handles are shared by item and skill tooltips. "
            "Skill-specific names, descriptions, effects and statuses are protected English."
        ),
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path(args.report).with_name("protected_skill_handles_effective.txt").write_text(
        "\n".join(sorted(skill_protected)) + "\n", encoding="utf-8"
    )
    Path(args.report).with_name("subtitle_handles.txt").write_text(
        "\n".join(sorted(out_sub_handles)) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
