# Seed data shipped with the installer

## voices/ — 기본 음성 여1~8 · 남1~7
Zeroth-Korean speech corpus (Lucas Jo, Wonkyum Lee), OpenSLR 40 / Hugging Face `kresnik/zeroth_korean`,
licensed CC BY 4.0. Two short utterances per speaker are used only as voice-cloning references; speaker numbers are in
each `voice.json` note. The nurse's own recordings are NOT part of this seed.

## noises/ — 병동 소음 클립
Ambient recordings used as background noise for STT training data (nebulizer, ICU background, patient-monitor alarm,
room tone, a synthesized rounds conversation). Included at the project owner's request so a fresh install has
realistic ward noise; the nebulizer/ICU/alarm clips were captured from online video and are redistributed here only
for this project's training-data purpose.
