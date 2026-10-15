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
