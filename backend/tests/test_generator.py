import random
from datetime import datetime

from nursing_tts.fake import random_datetime, random_form, random_patient
from nursing_tts.generator import Patient, build_script
from nursing_tts.templates import TEMPLATES, default_form

WHEN = datetime(2026, 10, 5, 10, 30)


def test_signal_line_format():
    s = build_script("s1", default_form("s1"), Patient(name="홍길동"), WHEN, seed=1)
    assert s.spoken_text.splitlines()[0] == "2026년 10월 5일 오전 10시 30분 홍길동 님 간호정보조사 기록입니다."
    assert s.tts_text.splitlines()[0] == "이천이십육년 시월 오일 오전 열 시 삼십 분 홍길동 님 간호정보조사 기록입니다."


def test_every_template_has_required_kind():
    kinds = {"간호정보조사", "퇴원간호", "수술전설명", "수술후설명", "인계"}
    for key, t in TEMPLATES.items():
        assert t.signal_kind in kinds, key
        s = build_script(key, default_form(key), Patient(op_date="10월 14일"), WHEN, seed=3)
        assert s.spoken_text.count("\n") >= 3
        assert "{" not in s.spoken_text and "}" not in s.spoken_text, s.spoken_text
        assert not any(line.endswith(",") for line in s.spoken_text.splitlines())


def test_seed_determinism_and_variety():
    f = default_form("s5")
    a = build_script("s5", f, Patient(), WHEN, seed=10).spoken_text
    b = build_script("s5", f, Patient(), WHEN, seed=10).spoken_text
    c = build_script("s5", f, Patient(), WHEN, seed=11).spoken_text
    assert a == b
    assert a != c


def test_random_forms_all_templates():
    rng = random.Random(123)
    for _ in range(30):
        for key in TEMPLATES:
            p = random_patient(rng, key)
            form = random_form(key, rng, p)
            s = build_script(key, form, p, random_datetime(rng), seed=rng.randrange(1 << 30))
            assert s.spoken_text.startswith(str(s.structured["datetime"][:4]))
            assert "{" not in s.spoken_text
            assert not any(ch.isdigit() for ch in s.tts_text), s.tts_text


def test_styles():
    f = default_form("s1")
    formal = build_script("s1", f, Patient(), WHEN, style="formal", seed=5).spoken_text
    assert "구요," not in formal and "고요," not in formal   # 격식체 run-ons use "~하였고," (user 2026-10-17)
