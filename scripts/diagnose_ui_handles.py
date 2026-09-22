import argparse, json, re, os
import xml.etree.ElementTree as ET
from pathlib import Path

TARGET_TEXTS = {
    "Attributes","Strength","Finesse","Intelligence","Constitution","Memory","Wits",
    "Damage","Critical Chance","Accuracy","Dodging","Physical Armour","Magic Armour",
    "Movement","Initiative","Experience","Next Level","Fire","Water","Earth","Air","Poison",
    "Civil Abilities","Personality","Craftsmanship","Nasty Deeds",
    "Bartering","Persuasion","Lucky Charm","Loremaster","Telekinesis","Sneaking","Thievery",
    "CHESTPLATE","HELMET","GLOVES","BOOTS","LEGGINGS","BELT","RING","AMULET","SHIELD",
}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--english",required=True)
    ap.add_argument("--root",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    rootxml=ET.parse(a.english).getroot()
    text_by_uid={}
    targets={}
    for e in rootxml.iter():
        if e.tag.endswith("content") and "contentuid" in e.attrib:
            uid=e.attrib["contentuid"]; txt=e.text or ""
            text_by_uid[uid]=txt
            if txt in TARGET_TEXTS:
                targets[uid]=txt
    pats={uid:uid.encode("ascii") for uid in targets}
    found={uid:[] for uid in targets}
    files_scanned=0
    bytes_scanned=0
    for p in Path(a.root).rglob("*"):
        if not p.is_file(): continue
        files_scanned+=1
        try:
            data=p.read_bytes()
        except Exception:
            continue
        bytes_scanned+=len(data)
        # quick prefilter
        if b"h" not in data: continue
        rel=p.relative_to(a.root).as_posix()
        for uid,b in pats.items():
            if b in data:
                found[uid].append(rel)
    report={
        "files_scanned":files_scanned,
        "bytes_scanned":bytes_scanned,
        "targets":[
            {"uid":uid,"text":targets[uid],"paths":found[uid]}
            for uid in sorted(targets,key=lambda u:(targets[u],u))
        ]
    }
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(report,indent=2),encoding="utf-8")
    for row in report["targets"]:
        if row["paths"]:
            print(row["text"],row["uid"],"::","; ".join(row["paths"][:20]))
    print("files",files_scanned,"bytes",bytes_scanned)

if __name__=="__main__":
    main()
