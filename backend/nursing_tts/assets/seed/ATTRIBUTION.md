# Seed data shipped with the installer

## voices/ — 기본 음성 여1~8 · 남1~7
Zeroth-Korean speech corpus (Lucas Jo, Wonkyum Lee), OpenSLR 40 / Hugging Face `kresnik/zeroth_korean`,
licensed CC BY 4.0. Two short utterances per speaker are used only as voice-cloning references; speaker numbers are in
each `voice.json` note. The nurse's own recordings are NOT part of this seed.

## noises/ — 병동 소음 클립
Background noise for STT training data, 24 kHz mono:
- 8 recordings made on the project owner's own ward on 2026-10-17 (nebulizer, infusion-pump alarm, patient-monitor
  alarm, oxygen flow at 3/5/9 L, two room-background takes with a nebulizer and people walking). Device and ambient
  sounds only, no speech or patient information. Provided by the owner for this project.
- room tone cut from the owner's own silent recording segments, and a synthesized rounds conversation (the owner's
  pseudonymous voice, pitch-shifted).
Earlier online-video clips (seed v1) were removed in seed v2.
