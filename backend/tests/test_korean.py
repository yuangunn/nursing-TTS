import random

from nursing_tts.korean import read_date, read_time, sino, native, to_tts_text, temperature_casual
from nursing_tts.grammar import close_sentence, fix_josa


def test_sino_native():
    assert sino(2026) == "이천이십육"
    assert sino(10000) == "만"
    assert sino(1800) == "천팔백"
    assert native(12) == "열두"
    assert native(20) == "스무"


def test_date_time():
    assert read_date(2026, 10, 5) == "이천이십육년 시월 오일"
    assert read_date(2026, 6, 1) == "이천이십육년 유월 일일"
    assert read_time(10, 30) == "오전 열 시 삼십 분"
    assert read_time(16, 10) == "오후 네 시 십 분"
    assert read_time(0, 5) == "오전 열두 시 오 분"


def test_to_tts_numbers_units_abbr():
    r = random.Random(0)
    out = to_tts_text("BP 135/80, HR 80, O2 3L, SpO2 99%, BT 37.2도, NRS 4점, 복도 2바퀴, 공 3개, 10월 13일", r)
    assert "백삼십오 에 팔십" in out
    assert "삼 리터" in out
    assert "삼십칠 점 이 도" in out
    assert "두 바퀴" in out and "세 개" in out
    assert "시월 십삼 일" in out
    assert "BP" not in out and "HR" not in out and "SpO2" not in out
    assert not any(ch.isdigit() for ch in out)


def test_temperature_casual():
    assert temperature_casual(37.4) == "7도 4"
    assert temperature_casual(38.0) == "8도"


def test_close_sentence():
    assert close_sentence("교육했고,") == "교육했습니다."
    assert close_sentence("PCA 유지 중이고,") == "PCA 유지 중입니다."
    assert close_sentence("수면 양호하시구요,") == "수면 양호하십니다."
    assert close_sentence("낙상 저위험이지만,") == "낙상 저위험입니다."
    assert close_sentence("끝났습니다.") == "끝났습니다."


def test_josa():
    assert fix_josa("위암(으)로") == "위암으로"
    assert fix_josa("36.9(으)로") == "36.9로"
    assert fix_josa("서울(으)로") == "서울로"
    assert fix_josa("DM(으)로") == "DM으로"
    assert fix_josa("틀니(이)랑 안경(이)랑") == "틀니랑 안경이랑"


def test_m2_chart_readings():
    """Readings collected in M2 (2026-10-15) from real-recording comparison and a 280-script audit."""
    r = random.Random(0)
    assert "백이십삼 에 구십" in to_tts_text("혈압 123/90", r)
    assert to_tts_text("체온 7도 1", r) == "체온 칠 도 일"
    assert to_tts_text("HTN", r) in ("에이치티엔", "하이퍼텐션")
    assert to_tts_text("1,800cc", r) == "천팔백 씨씨"
    assert to_tts_text("V/S 120/80-76-20-36.8", r) == "브이에스 백이십 에 팔십, 칠십육, 이십, 삼십육 점 팔"
    assert to_tts_text("메트로니다졸 q24h", r) == "메트로니다졸 이십사 시간마다"
    assert to_tts_text("BST 145mg/dL 측정됨", r) == "비에스티 백사십오 측정됨"
    assert to_tts_text("PRBC 1 pack 수혈 완료", r) == "피알비씨 한 팩 수혈 완료"
    assert to_tts_text("NSAIDs 알러지", r) == "엔세이드 알러지"
    assert to_tts_text("S상결장 종괴", r) == "에스상결장 종괴"
    assert "Total" not in to_tts_text("Total knee replacement arthroplasty", r)
    assert to_tts_text("Mastectomy 예정", r) == "마스텍토미 예정"


def test_tts_text_has_no_digits_or_latin_across_templates():
    from nursing_tts.fake import random_datetime, random_form, random_patient
    from nursing_tts.generator import build_script
    import re

    for t in ("s1", "s2", "s3_1", "s3_2", "s4", "s5", "s6"):
        for i in range(8):
            rng = random.Random(100 * i + len(t))
            p = random_patient(rng, t)
            s = build_script(t, random_form(t, rng, p), p, random_datetime(rng),
                             style=rng.choice(["mixed", "casual", "formal", "chart"]), seed=i, signal_format="random")
            left = re.findall(r"[A-Za-z0-9]+", s.tts_text)
            assert not left, f"{t} seed {i}: {left} in {s.tts_text!r}"


def test_ward_readings_pod_and_picc():
    r = random.Random(0)
    assert to_tts_text("POD 3 환자", r) == "피오디 삼일째 환자"
    assert to_tts_text("POD#2", r) == "피오디 이일째"
    assert to_tts_text("PICC 유지", r) == "피아이씨씨 유지"
