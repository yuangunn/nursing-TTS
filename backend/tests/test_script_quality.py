"""Scripts must not contain combinations a nurse would never chart (found by auditing 280 random scripts)."""
import random
import re
import zlib

from nursing_tts.fake import random_datetime, random_form, random_patient
from nursing_tts.generator import build_script

BAD = {
    "금연 금연": r"금연 금연", "숫자 뒤 이십니다": r"\d(?:\.\d)? ?이십니다", "측정한 측정한": r"(\S+) \1\b",
    "PCA 없이 PCA 교육": r"진통제 없이.*PCA 버튼", "의식 저하인데 대답": r"(stupor|confuse).*적절히 대답",
    "금식인데 식사": r"금식 유지.*(전량|절반) (섭취|드)", "소변줄 없는데 도뇨관 간호": r"소변줄 없이.*(도뇨관 (제거|고정|확인)|회음부)",
    "배액관 없는데 JP": r"배액관 없.*JP \d", "변화 없음 있": r"변화 없음 있", "풀코드": r"풀 ?코드|full code",
    "재사정이 더 아픔": r"통증 (\d+)점으로 (감소|호전)",
    "없음에 어미 붙음": r"없음(하여|으로|이고|이구요| 나왔)",
}


def _scripts(n_per_template=30):
    for t in ["s1", "s2", "s3_1", "s3_2", "s4", "s5", "s6"]:
        for i in range(n_per_template):
            rng = random.Random(7919 * i + zlib.crc32(t.encode()) % 997)
            p = random_patient(rng, t)
            s = build_script(t, random_form(t, rng, p), p, random_datetime(rng),
                             style=rng.choice(["mixed", "casual", "formal", "chart"]), seed=i, signal_format="random")
            yield t, p, s.spoken_text.replace("\n", " ")


def test_no_contradictory_or_awkward_sentences():
    hits = []
    for t, p, text in _scripts():
        for name, pat in BAD.items():
            m = re.search(pat, text)
            if not m:
                continue
            if name == "측정한 측정한" and m.group(1) in ("금연", "매우", "조금", "자주", "잘", "안"):  # legitimate repeats
                continue
            if name == "재사정이 더 아픔":
                before = re.search(r"(\d+)점(?:으로 사정함|\.)", text[: m.start()])
                if not before or int(m.group(1)) < int(before.group(1)):
                    continue
            hits.append((name, t, text[max(0, m.start() - 50): m.end() + 30]))
    assert not hits, "\n".join(f"{n} / {t}: …{s}…" for n, t, s in hits[:12])


def test_discharge_and_chemo_records_have_no_pca_or_catheter_items():
    for t, p, text in _scripts(20):
        if t == "s4":
            assert "PCA" not in text, text
        if p.kind == "chemo":
            assert "PCA" not in text and "도뇨관" not in text and "소변줄" not in text and "POD" not in text, text


def test_rare_states_are_rare():
    n = dnr = iso = 0
    for t, p, text in _scripts(40):
        if t != "s5":
            continue
        n += 1
        dnr += ("DNR" in text) or ("연명의료" in text)
        iso += ("격리 중" in text) or ("격리 적용" in text) or ("격리 환자" in text)
    assert dnr / n < 0.35 and iso / n < 0.35, (dnr, iso, n)


def test_young_non_ortho_patients_walk_independently():
    import random
    from nursing_tts.fake import random_form, random_patient
    rng = random.Random(9)
    n = dep = 0
    for _ in range(300):
        p = random_patient(rng, "s1")
        if p.department == "정형외과" or (p.age or 0) >= 70:
            continue
        f = random_form("s1", rng, p)
        n += 1
        dep += f.get("mobility") != "independent" or f.get("adl") != "independent"
    assert n > 50 and dep / n < 0.25, (dep, n)


def test_fall_and_pressure_scores_match_their_risk_bands():
    import random
    from nursing_tts.fake import braden_risk, fall_level, random_form, random_patient
    from nursing_tts.generator import build_script
    from nursing_tts.fake import random_datetime
    rng = random.Random(4)
    levels = set()
    for _ in range(200):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        assert f["fall"] == fall_level(f["jhfrat"]), (f["jhfrat"], f["fall"])
        levels.add(f["fall"])
        if f.get("skin") == "pressure":
            assert f["braden"] <= 14
        if "p_braden" in f:
            assert f["p_braden_risk"] == braden_risk(f["p_braden"])
        s = build_script("s1", f, p, random_datetime(rng), style="formal", seed=1)
        assert "Morse" not in s.spoken_text and "모스" not in s.spoken_text
        for w in ("Braden", "존스홉킨스", "JHFRAT", "브레이든"):
            assert w not in s.spoken_text, (w, s.spoken_text)          # ward talk: "낙상 n점으로 중위험군", never the tool name
        assert re.search(r"낙상 \d+점으로 .*위험", s.spoken_text) or "낙상 " in s.spoken_text, s.spoken_text
        assert f["pressure_risk"] == {"최고위험": "very_high", "고위험": "high", "중등도 위험": "moderate", "저위험": "low", "위험 없음": "none"}[braden_risk(f["braden"])]
        if f["fall"] != "high":
            assert not any(k.startswith("p_fall_") for k in f), [k for k in f if k.startswith("p_fall_")]
    assert {"low", "moderate", "high"} <= levels
    for t in ("s5", "s3_1", "s6"):
        for _ in range(60):
            p = random_patient(rng, t)
            f = random_form(t, rng, p)
            if "p_jhfrat" in f:
                assert f["p_jhfrat"] >= 14
            if "p_braden" in f:
                assert f["p_braden_risk"] == braden_risk(f["p_braden"])
