import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

TALENT_NAMES = [
    "All Skilled Up",
    "Ambidextrous",
    "Ancestral Knowledge",
    "Arrow Recovery",
    "Bigger and Better",
    "Bigger And Better",
    "Comeback Kid",
    "Corpse Eater",
    "Demon",
    "Duck Duck Goose",
    "Dwarven Guile",
    "Elemental Affinity",
    "Elemental Ranger",
    "Escapist",
    "Executioner",
    "Far Out Man",
    "Five-Star Diner",
    "Glass Cannon",
    "Guerrilla",
    "Guerilla",
    "Hothead",
    "Ice King",
    "Ingenious",
    "Leech",
    "Living Armour",
    "Living Armor",
    "Lone Wolf",
    "Mnemonic",
    "Morning Person",
    "Opportunist",
    "Parry Master",
    "Pet Pal",
    "Picture of Health",
    "Savage Sortilege",
    "Slingshot",
    "Sophisticated",
    "Spellsong",
    "Stench",
    "Sturdy",
    "The Pawn",
    "Thrifty",
    "Torturer",
    "Undead",
    "Unstable",
    "Walk It Off",
    "What A Rush",
    "What a Rush",
]

def parse(path):
    root = ET.parse(path).getroot()
    rows = []
    for e in root.iter():
        if e.tag.endswith("content") and "contentuid" in e.attrib:
            rows.append((e.attrib["contentuid"], e.text or ""))
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", required=True)
    ap.add_argument("--thai", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    off = parse(Path(args.official))
    th = dict(parse(Path(args.thai)))
    by_text = {}
    for uid, txt in off:
        by_text.setdefault(txt, []).append(uid)

    report = []
    for name in TALENT_NAMES:
        uids = by_text.get(name, [])
        if not uids:
            continue
        report.append({
            "official_name": name,
            "matches": len(uids),
            "entries": [
                {"uid": uid, "thai_value": th.get(uid, "")}
                for uid in uids
            ],
        })

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))

if __name__ == "__main__":
    main()
