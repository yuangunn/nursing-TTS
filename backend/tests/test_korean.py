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
