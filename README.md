# DOS2 Hybrid Thai / English Builder

Automated, fail-closed builder for a Divinity: Original Sin 2 Definitive Edition hybrid localization.

## Policy

- Official English localization is the baseline.
- Thai v1.3 is used only for:
  - NPC/player dialogue and narrator text selected by the dialogue whitelist
  - books, letters, notes, journals and other readable documents selected by the readable whitelist
  - cinematic subtitle resources
- UI, menus, skills, statuses, items, talents, attributes, recipes, crafting, combat/system terms and quest log/objectives remain Official English unless explicitly whitelisted.

## Build guarantees

The workflow validates localization UID counts and uniqueness, checks Thai/English UID alignment, rejects the known suspicious Thai corruption handle if selected, preserves non-whitelisted localization values, builds a DOS2DE package with LSLib, round-trip extracts it, and compares the extracted package payload with the staged hybrid payload.

Build products are uploaded as GitHub Actions artifacts:
- `English.pak`
- installable ZIP including the Thai font assets
- whitelist/QA reports

The input files are downloaded from the persistent Google Drive build workspace used for this project.
