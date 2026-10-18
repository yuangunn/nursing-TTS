"""Korean reading rules: numbers, dates, units and medical abbreviations.

Two text layers are produced for every recording:

* ``spoken_text``  - the ground-truth transcript as a nurse would *write* what
  she said ("혈압 123에 78, HTN 있으시고 ...").  Digits and abbreviations stay.
* ``tts_text``     - a fully phonetic Korean rendering of the same utterance that
  a Korean TTS model can read without guessing ("혈압 백이십삼에 칠십팔,
  에이치티엔 있으시고 ...").

This module implements the spoken -> tts conversion.
"""
from __future__ import annotations

import random
import re
from typing import Iterable

# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

SINO_DIGITS = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
SINO_UNITS = ["", "십", "백", "천"]
SINO_BIG = ["", "만", "억", "조"]

NATIVE_ONES = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
NATIVE_TENS = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]

# Counters that take native Korean numerals (한 개, 두 번, 세 시 ...)
NATIVE_COUNTERS = {
    "개", "명", "번", "바퀴", "살", "시간", "달", "마리", "잔", "알", "봉", "장",
    "시", "군데", "가지", "차례", "분(사람)", "갑", "컵", "숟가락", "스푼", "팩",
}
# Counters that always take Sino numerals even though they look like counts.
SINO_COUNTERS = {
    "회", "세", "일", "월", "년", "분", "초", "점", "도", "층", "호", "주", "차",
    "kg", "cm", "mm", "mg", "g", "cc", "ml", "mL", "L", "%", "mmHg", "Fr", "단계",
    "병동", "인분", "mL/hr", "cc/hr", "ml/hr", "G", "유닛", "unit", "IU", "mcg", "㎍", "mEq",
}


def sino(n: int) -> str:
    """Read an integer with Sino-Korean numerals (0 -> 영)."""
    if n == 0:
        return "영"
    if n < 0:
        return "마이너스 " + sino(-n)
    parts: list[str] = []
    big_idx = 0
    while n > 0:
        chunk = n % 10000
        if chunk:
            s = _sino_chunk(chunk, first_big=(big_idx == 0))
            if big_idx > 0 and chunk == 1:
                s = ""  # 만, 억 without leading 일 (일만 -> 만)
            parts.append(s + SINO_BIG[big_idx])
        n //= 10000
        big_idx += 1
    return "".join(reversed(parts))


def _sino_chunk(n: int, first_big: bool = True) -> str:
    out = ""
    for i in range(3, -1, -1):
        d = (n // (10 ** i)) % 10
        if d == 0:
            continue
        if d == 1 and i > 0:
            out += SINO_UNITS[i]  # 십, 백, 천 (not 일십)
        else:
            out += SINO_DIGITS[d] + SINO_UNITS[i]
    return out


def native(n: int, attributive: bool = True) -> str:
    """Read 1..99 with native Korean numerals.

    ``attributive`` selects the determiner form used before counters
    (한/두/세/네/스무) rather than the standalone form (하나/둘/셋/넷/스물).
    """
    if n <= 0 or n >= 100:
        return sino(n)
    tens, ones = divmod(n, 10)
    if not attributive:
        standalone = ["", "하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉"]
        if tens == 2 and ones == 0:
            return "스물"
        return NATIVE_TENS[tens] + standalone[ones]
    if tens == 2 and ones == 0:
        return "스무"
    return NATIVE_TENS[tens] + NATIVE_ONES[ones]


def digits(s: str) -> str:
    """Read digit by digit (phone numbers, IDs). 0 -> 공."""
    table = ["공", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
    return " ".join(table[int(c)] if c.isdigit() else c for c in s)


def read_number(token: str, counter: str | None = None) -> str:
    """Read a number token (int, decimal) given the following counter word."""
    if "." in token:
        whole, frac = token.split(".", 1)
        w = sino(int(whole)) if whole else "영"
        return f"{w} 점 {digits(frac).replace(' ', '')}"
    n = int(token)
    if counter and counter in NATIVE_COUNTERS and n < 100:
        return native(n)
    if counter == "시" and n < 100:
        return native(n)
    return sino(n)


# ---------------------------------------------------------------------------
# Units and symbols
# ---------------------------------------------------------------------------

UNIT_READINGS: dict[str, list[str]] = {
    "mmHg": [""],  # nurses almost never pronounce it
    "mg/dL": [""],  # "혈당 145" - the unit is written, not said
    "mg/m²": ["밀리그램 퍼 제곱미터", "밀리그램"],
    "mg/kg": ["밀리그램 퍼 킬로", "밀리그램 퍼 킬로그램"],
    "cc": ["씨씨"],
    "cc/hr": ["씨씨 퍼 아워", "씨씨"],
    "mL/hr": ["밀리리터 퍼 아워", "씨씨"],
    "ml/hr": ["밀리리터 퍼 아워", "씨씨"],
    "mL": ["밀리리터", "씨씨"],
    "ml": ["밀리리터", "씨씨"],
    "L": ["리터"],
    "L/min": ["리터", "리터 퍼 미닛"],
    "mg": ["밀리그램", "미리그램"],
    "mcg": ["마이크로그램"],
    "g": ["그램"],
    "kg": ["킬로", "킬로그램"],
    "cm": ["센치", "센티"],
    "mm": ["밀리"],
    "%": ["퍼센트", "프로"],
    "Fr": ["프렌치"],
    "G": ["게이지"],
    "IU": ["아이유"],
    "unit": ["유닛"],
    "mEq": ["밀리이퀴"],
    "℃": ["도"],
    "°C": ["도"],
}

# ---------------------------------------------------------------------------
# Abbreviations and English medical vocabulary -> Korean pronunciation(s)
# ---------------------------------------------------------------------------

ABBREVIATIONS: dict[str, list[str]] = {
    # vitals
    "BP": ["비피"], "HR": ["에이치알"], "PR": ["피알"], "RR": ["알알"], "BT": ["비티"],
    "SpO2": ["에스피오투", "샛", "새츄레이션"], "SPO2": ["에스피오투"], "V/S": ["바이탈", "브이에스"],
    "SBP": ["에스비피"], "DBP": ["디비피"], "MAP": ["맵"], "BST": ["비에스티"],
    # diagnosis / history
    "HTN": ["에이치티엔", "하이퍼텐션"], "DM": ["디엠"], "CKD": ["씨케이디"], "COPD": ["씨오피디"],
    "CVA": ["씨브이에이"], "MI": ["엠아이"], "CAD": ["씨에이디"], "Af": ["에이에프"], "AF": ["에이에프"],
    "TB": ["티비"], "Hx": ["히스토리"], "PHx": ["피 히스토리"], "op": ["옵"], "Op": ["옵"], "OP": ["옵"],
    "Dx": ["디엑스", "진단"], "Tx": ["트리트먼트"], "Bx": ["바이옵시"],
    "CA": ["씨에이", "암"], "ca": ["씨에이"], "cancer": ["캔서"],
    "AGC": ["에이지씨"], "EGC": ["이지씨"],
    # surgery
    "TG": ["티지"], "STG": ["에스티지"], "DG": ["디지"], "LAR": ["엘에이알"], "AR": ["에이알"],
    "POD": ["피오디"], "OR": ["오알"], "RR room": ["회복실"], "PACU": ["파쿠", "피에이씨유"],
    "ICU": ["아이씨유"], "ER": ["이알", "응급실"], "OPD": ["오피디", "외래"],
    "Laparoscopic": ["라파로스코픽", "라파"], "laparoscopic": ["라파로스코픽", "라파"], "lapa": ["라파"],
    "total": ["토탈"], "subtotal": ["서브토탈"], "distal": ["디스탈"],
    "gastrectomy": ["가스트렉토미"], "colectomy": ["콜렉토미"], "hemicolectomy": ["헤미콜렉토미"],
    "cholecystectomy": ["콜리시스텍토미"], "appendectomy": ["아펜덱토미"], "lobectomy": ["로벡토미"],
    "mastectomy": ["마스텍토미"], "hysterectomy": ["히스테렉토미"], "TKRA": ["티케이알에이"], "THRA": ["티에이치알에이"],
    "Whipple": ["휘플"], "PPPD": ["피피피디"],
    # pain / meds
    "PCA": ["피씨에이"], "NRS": ["엔알에스"], "VAS": ["바스"], "PRN": ["피알엔"], "prn": ["피알엔"],
    "IV": ["아이브이"], "iv": ["아이브이"], "PO": ["피오"], "po": ["피오"], "IM": ["아이엠"], "SC": ["에스씨"],
    "q8h": ["큐 에이트 아워", "팔 시간마다"], "q6h": ["큐 식스 아워", "여섯 시간마다"],
    "q12h": ["큐 트웰브 아워", "열두 시간마다"], "q4h": ["큐 포 아워", "네 시간마다"],
    "qd": ["큐디", "하루 한 번"], "bid": ["비아이디", "하루 두 번"], "tid": ["티아이디", "하루 세 번"],
    "qid": ["큐아이디", "하루 네 번"], "hs": ["에이치에스"], "ac": ["에이씨"], "pc": ["피씨"],
    "acetaminophen": ["아세트아미노펜"], "Acetaminophen": ["아세트아미노펜"],
    "tramadol": ["트라마돌"], "ketorolac": ["케토롤락"], "fentanyl": ["펜타닐"], "morphine": ["몰핀"],
    "cefazolin": ["세파졸린"], "ceftriaxone": ["세프트리악손"], "metronidazole": ["메트로니다졸"],
    "metformin": ["메트포르민"], "amlodipine": ["암로디핀"], "aspirin": ["아스피린"],
    "insulin": ["인슐린"], "heparin": ["헤파린"], "enoxaparin": ["에녹사파린"], "warfarin": ["와파린"],
    "Hartmann": ["하트만"], "hartmann": ["하트만"], "H/S": ["하프 세일라인", "에이치에스"],
    "N/S": ["노말 세일라인", "엔에스"], "NS": ["엔에스"], "DW": ["디더블유"], "D5W": ["디파이브더블유"],
    "5DW": ["파이브 디더블유"], "10DW": ["텐 디더블유"], "TPN": ["티피엔"], "PN": ["피엔"],
    "SSI": ["에스에스아이", "슬라이딩"], "RI": ["알아이"],
    "Lasix": ["라식스"], "KCl": ["케이씨엘"], "NaCl": ["엔에이씨엘"], "MgSO4": ["마그네슘"],
    # lines / tubes / drains
    "JP": ["제이피"], "PIV": ["피아이브이", "말초 라인"], "PICC": ["피아이씨씨"], "C-line": ["씨라인"],  # "픽"은 이 병동에서 안 씀
    "CVC": ["씨브이씨"], "Foley": ["폴리"], "foley": ["폴리"], "catheter": ["카테터"],
    "L-tube": ["엘튜브"], "NG": ["엔지"], "NGT": ["엔지티"], "T-tube": ["티튜브"], "PCD": ["피씨디"],
    "PTBD": ["피티비디"], "ENBD": ["이엔비디"], "chest tube": ["체스트 튜브"], "Rt": ["라이트"], "Lt": ["레프트"],
    "Rt.": ["라이트"], "Lt.": ["레프트"], "arm": ["암"], "Fr.": ["프렌치"],
    "sanguineous": ["생기너스"], "serosanguineous": ["시로생기너스"], "serous": ["시러스"],
    "bloody": ["블러디"], "turbid": ["터비드"], "straw": ["스트로우"], "pinkish": ["핑키시"], "orange": ["오렌지"],
    "Good sleep pattern": ["굿 슬립 패턴"], "good sleep pattern": ["굿 슬립 패턴"],
    "oozing": ["우징"], "pus": ["퍼스"], "bile": ["바일"], "purulent": ["퓨룰런트"],
    "dressing": ["드레싱"], "stapler": ["스테플러"], "steri-strip": ["스테리스트립"],
    # respiratory
    "O2": ["오투"], "nasal": ["나잘", "네이잘"], "trach mask": ["트라키 마스크", "트랙 마스크"], "portable": ["포터블"], "3-way": ["쓰리웨이"], "mask": ["마스크"], "room air": ["룸 에어"], "RA": ["룸 에어"],
    "inspirometer": ["인스피로미터"], "Inspirometer": ["인스피로미터"], "nebulizer": ["네뷸라이저"],
    "lung care": ["렁 케어"], "ambulation": ["앰뷸레이션"], "chest PA": ["체스트 피에이"],
    "CXR": ["씨엑스알"], "CT": ["씨티"], "MRI": ["엠알아이"], "EKG": ["이케이지"], "ECG": ["이씨지"],
    "ABGA": ["에이비지에이"], "PFT": ["피에프티"], "echo": ["에코"],
    # labs
    "Lab": ["랩"], "lab": ["랩"], "WBC": ["더블유비씨"], "Hb": ["헤모글로빈", "에이치비"], "Hct": ["헤마토크릿"],
    "PLT": ["플레이틀렛", "피엘티"], "CRP": ["씨알피"], "ESR": ["이에스알"], "BUN": ["번"], "Cr": ["크레아티닌"],
    "Na": ["나트륨", "소디움"], "K": ["포타슘", "케이"], "Cl": ["클로라이드"], "Ca": ["칼슘"], "Mg": ["마그네슘"],
    "AST": ["에이에스티"], "ALT": ["에이엘티"], "ALP": ["에이엘피"], "T-bil": ["티빌"], "albumin": ["알부민"],
    "PT": ["피티"], "aPTT": ["에이피티티"], "INR": ["아이엔알"], "glucose": ["글루코스"], "HbA1c": ["당화혈색소", "에이원씨"],
    "CBC": ["씨비씨"], "LFT": ["엘에프티"], "RFT": ["알에프티"], "culture": ["컬쳐"], "F/U": ["에프유", "팔로업"],
    "iPTH": ["아이피티에이치"], "urine analysis": ["유린 어날리시스", "소변 검사"], "urine": ["유린"], "analysis": ["어날리시스"],
    "f/u": ["에프유", "팔로업"], "noti": ["노티"], "Noti": ["노티"], "notify": ["노티파이"],
    "I/O": ["아이오", "인풋 아웃풋"], "I&O": ["아이오"], "UO": ["유오"],
    # status
    "NPO": ["엔피오", "금식"], "SOW": ["에스오더블유", "물"], "LD": ["엘디"], "SD": ["에스디"], "GD": ["지디"],
    "gas out": ["가스 아웃"], "gas": ["가스"], "out": ["아웃"], "self": ["셀프"], "self voiding": ["셀프 보이딩"],
    "voiding": ["보이딩"], "mental": ["멘탈"], "alert": ["얼러트"], "drowsy": ["드라우지"], "stupor": ["스투퍼"],
    "confuse": ["컨퓨즈"], "delirium": ["딜리리움"], "DNR": ["디엔알"], "full code": ["풀 코드"],
    "Full code": ["풀 코드"], "code": ["코드"], "Braden": ["브레이든"], "Morse": ["모스"], "JHFRAT": ["존스홉킨스 낙상 평가", "제이에이치프랫"], "Johns Hopkins": ["존스홉킨스"], "GCS": ["지씨에스"],
    "SBAR": ["에스바"], "ADL": ["에이디엘"], "ROM": ["롬"], "DVT": ["디브이티"], "IPC": ["아이피씨"], "ice bag": ["아이스백"], "CPM": ["씨피엠"],
    "EDR": ["이디알"], "EMR": ["이엠알"], "OCS": ["오씨에스"], "sliding": ["슬라이딩"], "scale": ["스케일"],
    "dumping": ["덤핑"], "chemo": ["케모", "항암"], "regimen": ["레지멘"], "FOLFOX": ["폴폭스"], "XELOX": ["젤록스"],
    "cycle": ["사이클"], "day": ["데이"], "Day": ["데이"], "D": ["디"],
    "teach-back": ["티치백"], "teach back": ["티치백"], "dc": ["디씨"], "d/c": ["디씨"], "D/C": ["디씨"],
    "Discharge": ["디스차지"], "discharge": ["디스차지"], "check": ["체크"], "hold": ["홀드"], "keep": ["킵"],
    "apply": ["어플라이"], "remove": ["리무브"], "change": ["체인지"], "intensive": ["인텐시브"], "deep": ["딥"],
    "breathing": ["브리딩"], "Rh": ["알에이치"], "Rh+": ["알에이치 플러스"], "A형": ["에이형"], "B형": ["비형"],
    "AB형": ["에이비형"], "O형": ["오형"], "EGD": ["이지디"], "colono": ["콜로노"], "ERCP": ["이알씨피"],
    "PEG": ["페그"], "TACE": ["테이스"], "RFA": ["알에프에이"], "angio": ["안지오"], "PCI": ["피씨아이"],
    "CAG": ["씨에이지"], "PTCA": ["피티씨에이"], "biopsy": ["바이옵시"], "pending": ["펜딩"],
    # words the 2026-10-15 M2 audit found left untranslated in tts_text (280 random scripts)
    "blood culture": ["블러드 컬쳐"], "urine culture": ["유린 컬쳐"], "wound culture": ["운드 컬쳐"],
    "PRBC": ["피알비씨"], "pack": ["팩"], "ice pack": ["아이스팩"], "5 rights": ["파이브 라이츠"],
    "NSAIDs": ["엔세이드"], "PAINAD": ["페인에이디"], "FLACC": ["플랙"], "ORIF": ["오알아이에프", "오리프"],
    "arthroplasty": ["아스로플라스티"], "replacement": ["리플레이스먼트"], "knee": ["니"], "hip": ["힙"],
    "shoulder": ["숄더"], "ankle": ["앵클"], "anterior": ["앤테리어"], "resection": ["리섹션"], "low": ["로우"],
    "thyroidectomy": ["타이로이덱토미"], "hepatectomy": ["헤파텍토미"], "cataract": ["카타락트"], "surgery": ["서저리"],
    "chole": ["콜레"], "appe": ["아페"], "lap": ["랩"], "S상": ["에스상"], "A-line": ["에이라인"],
    "IV line": ["아이브이 라인"], "IV site": ["아이브이 사이트"], "line": ["라인"], "site": ["사이트"],
    "gauge": ["게이지"], "patency": ["페이턴시"], "call bell": ["콜벨"], "milking": ["밀킹"],
    "clean": ["클린"], "clear": ["클리어"], "soft": ["소프트"], "crackle": ["크래클"], "distension": ["디스텐션"],
    "high flow": ["하이 플로우"], "simple mask": ["심플 마스크"], "reservoir mask": ["리저버 마스크"],
    "nasal cannula": ["네이잘 캐뉼라"], "cannula": ["캐뉼라"], "bilious": ["빌리어스"], "Penrose": ["펜로즈"],
    "Hemovac": ["헤모박"], "wound": ["운드"], "right": ["라이트"], "left": ["레프트"], "sputum": ["스퓨텀"],
    "Nelaton": ["넬라톤"], "suprapubic": ["수프라퓨빅"], "stable": ["스테이블"],
    # ward chart shorthand (clinical.py scenarios): "TM c ALND" = with, SLNB, Hemovac, CPM ...
    "partial": ["파셜"], "excision": ["익시전"], "mass": ["매스"], "bilateral": ["바이래터럴", "양측"], "breast": ["브레스트"], "rectal": ["렉탈"],
    "c": ["씨", "위드"], "ALND": ["에이엘엔디", "액와 림프절 절제"], "SLNB": ["에스엘엔비", "감시림프절 생검"], "NSM": ["엔에스엠"],
    "BTT": ["비티티"], "MRND": ["엠알엔디"], "LAR": ["엘에이알"], "RHC": ["알에이치씨", "우측 결장절제"], "ileostomy": ["아일리오스토미", "회장루"],
    "hernioplasty": ["허니오플라스티", "탈장 교정"], "prolapse": ["프롤랩스"], "TLH": ["티엘에이치"], "BSO": ["비에스오"], "TAH": ["티에이에이치"],
    "staging": ["스테이징"], "laparotomy": ["라파로토미"], "C-sec": ["씨섹", "제왕절개"], "BOCE": ["비오씨이"], "myomectomy": ["마이오멕토미"],
    "TURB": ["터브", "티유알비"], "RALRP": ["랄프", "알에이엘알피"], "nephrectomy": ["네프렉토미"], "ESS": ["이에스에스"],
    "tracheostomy": ["트라케오스토미", "기관절개"], "TKA": ["티케이에이"], "THA": ["티에이치에이"], "TSA": ["티에스에이"],
    "meniscectomy": ["메니섹토미"], "meniscal": ["메니스칼"], "repair": ["리페어"], "BKA": ["비케이에이"], "rotator cuff": ["로테이터 커프"],
    "cuff": ["커프"], "rotator": ["로테이터"], "reconstruction": ["리컨스트럭션"], "recon": ["리컨"], "Hemovac": ["헤모박"], "CPM": ["씨피엠"],
    "CBI": ["씨비아이", "방광 세척"], "CMS": ["씨엠에스"], "ANC": ["에이엔씨"], "EF": ["이에프"], "G-CSF": ["지씨에스에프"], "mFOLFOX6": ["엠폴폭스", "엠폴폭스 식스", "폴폭스"],
    "mFOLFIRI": ["엠폴피리", "엠폴피리", "폴피리"], "FOLFIRI": ["폴피리"], "FOLFIRINOX": ["폴피리녹스"], "A-FOLFIRI": ["에이폴피리", "에이폴피리", "아바스틴 폴피리"], "E-FOLFIRI": ["이폴피리", "이폴피리", "얼비툭스 폴피리"],
    "TCHP": ["티씨에이치피"], "TCH": ["티씨에이치"], "HP": ["에이치피"], "AC": ["에이씨"], "K+AC": ["키트루다 에이씨", "키트루다 플러스 에이씨", "케이 에이씨"], "H": ["허셉틴", "에이치"],
    "K+TC": ["키트루다 티씨", "키트루다 플러스 티씨", "케이 티씨"], "T+C+Jemperli": ["티씨 젬펄리", "티 씨 젬펄리", "파클리탁셀 카보플라틴 젬펄리"], "Jemperli": ["젬펄리"],
    "HER2": ["허투"], "dMMR": ["디엠엠알"], "RAS": ["라스"], "BRCA": ["브라카"], "PSA": ["피에스에이"], "DIEP": ["딥"], "LD": ["엘디"], "TSH": ["티에스에이치"],
    "Mg": ["마그네슘"], "AUC": ["에이유씨"], "AUC5": ["에이유씨 파이브"], "AUC6": ["에이유씨 식스"], "kg": ["킬로그램"], "m²": ["제곱미터"],
}
# Surgery names as the ward says them (user, 2026-10-16): letters, Korean name, or a mix — "티에이치에이",
# "인공고관절 수술", "고관절 티에이치에이"; "라파 꼴레", "담낭절제", "복강경적 담낭절제술". Both the chart key
# and the handover abbreviation spelling are listed because multi-word keys match case-sensitively.
_SURGERY_READINGS: list[tuple[tuple[str, ...], list[str]]] = [
    (("THA",), ["티에이치에이", "고관절 인공관절 수술", "인공고관절 수술", "고관절 티에이치에이"]),
    (("TKA",), ["티케이에이", "무릎 인공관절 수술", "인공슬관절 수술", "무릎 티케이에이"]),
    (("TSA",), ["티에스에이", "어깨 인공관절 수술", "인공견관절 수술"]),
    (("Lapa chole", "lapa chole"), ["라파 꼴레", "라파 콜레", "담낭절제", "복강경적 담낭절제술", "복강경 담낭절제"]),
    (("Lapa RHC", "lapa RHC"), ["라파 알에이치씨", "복강경 우측 결장절제", "라파 라이트 헤미", "우측 결장절제술"]),
    (("LAR",), ["엘에이알", "저위전방절제술", "엘에이알 수술"]),
    (("Total mastectomy c ALND", "TM c ALND"), ["티엠 씨 에이엘엔디", "토탈 마스텍토미 위드 에이엘엔디", "유방 전절제 에이엘엔디", "유방 전절제술"]),
    (("Partial mastectomy c SLNB", "partial mastectomy c SLNB"), ["파셜 마스텍토미 위드 에스엘엔비", "유방 부분절제 에스엘엔비", "유방 부분절제술", "파셜 마스텍토미"]),
    (("NSM c SLNB",), ["엔에스엠 위드 에스엘엔비", "엔에스엠", "유두보존 유방절제 에스엘엔비"]),
    (("Breast mass excision", "breast mass excision"), ["브레스트 매스 익시전", "유방 종괴 절제", "매스 익시전"]),
    (("Bilateral total thyroidectomy", "BTT"), ["비티티", "갑상선 전절제", "갑상선 전절제술", "바이래터럴 토탈 타이로이덱토미"]),
    (("MRND",), ["엠알엔디", "경부 림프절 절제술"]),
    (("Ileostomy repair", "ileostomy repair"), ["아일리오스토미 리페어", "회장루 복원", "장루 복원술"]),
    (("Hernioplasty", "hernioplasty"), ["허니오플라스티", "탈장 교정술", "탈장 수술", "헤르니아 수술"]),
    (("Rectal prolapse OP", "rectal prolapse OP"), ["렉탈 프롤랩스 오피", "직장탈출증 수술", "직장 탈출 교정술"]),
    (("TLH c BSO",), ["티엘에이치 위드 비에스오", "티엘에이치 비에스오", "복강경 전자궁절제 양측 부속기절제", "티엘에이치"]),
    (("TAH",), ["티에이에이치", "개복 전자궁절제술", "개복 자궁절제"]),
    (("Staging laparotomy", "staging lapa"), ["스테이징 라파로토미", "스테이징 라파", "병기설정 개복술", "스테이징 수술"]),
    (("C-sec",), ["씨섹", "제왕절개", "씨섹션"]),
    (("Lapa BOCE", "lapa BOCE"), ["라파 비오씨이", "복강경 양측 난소낭종절제", "난소 낭종 절제술"]),
    (("Myomectomy", "myomectomy"), ["마이오멕토미", "자궁근종절제술", "근종 절제"]),
    (("TURB",), ["터브", "티유알비", "경요도 방광종양절제술", "방광종양 절제"]),
    (("RALRP",), ["랄프", "알에이엘알피", "로봇 전립선절제술", "로봇 근치적 전립선절제술"]),
    (("Partial nephrectomy", "partial nephrectomy"), ["파셜 네프렉토미", "부분 신장절제술", "신장 부분절제"]),
    (("ESS",), ["이에스에스", "내시경 부비동 수술", "부비동 내시경 수술"]),
    (("Tracheostomy", "tracheostomy"), ["트라케오스토미", "기관절개술", "기관절개"]),
    (("Meniscectomy", "meniscectomy"), ["메니섹토미", "반월상연골 절제술", "관절경 연골 절제"]),
    (("Meniscal repair", "meniscal repair"), ["메니스칼 리페어", "반월상연골 봉합술", "연골판 봉합"]),
    (("ORIF",), ["오알아이에프", "오리프", "관혈적 정복 내고정술", "골절 금속판 고정 수술"]),
    (("BKA",), ["비케이에이", "무릎 아래쪽 절단"]),
    (("Rotator cuff repair", "rotator cuff repair"), ["로테이터 커프 리페어", "회전근개 봉합술", "어깨 회전근개 봉합", "로테이터 커프 수술"]),
    (("Breast reconstruction", "breast recon"), ["브레스트 리컨스트럭션", "브레스트 리컨", "유방 재건술", "유방 재건"]),
    (("Hemorrhoidectomy", "hemorrhoidectomy"), ["헤모로이덱토미", "치핵 절제술", "치질 수술", "헤모 수술"]),
    (("hemorrhoid",), ["헤모로이드", "치핵"]),
    (("drain",), ["드레인"]), (("drainage",), ["드레니지"]), (("forearm",), ["포암"]), (("hand",), ["핸드"]),
]
for _names, _readings in _SURGERY_READINGS:
    for _n in _names:
        ABBREVIATIONS[_n] = _readings

# Case-insensitive fallback for leftovers ("Mastectomy", "Total" ...); exact keys win first.
_ABBR_LOWER: dict[str, list[str]] = {}
for _k, _v in ABBREVIATIONS.items():
    _ABBR_LOWER.setdefault(_k.lower(), _v)

LETTER_READING = {
    "A": "에이", "B": "비", "C": "씨", "D": "디", "E": "이", "F": "에프", "G": "지", "H": "에이치",
    "I": "아이", "J": "제이", "K": "케이", "L": "엘", "M": "엠", "N": "엔", "O": "오", "P": "피",
    "Q": "큐", "R": "알", "S": "에스", "T": "티", "U": "유", "V": "브이", "W": "더블유", "X": "엑스",
    "Y": "와이", "Z": "지",
}


def spell_letters(token: str) -> str:
    return "".join(LETTER_READING.get(c.upper(), c) for c in token)


# Longest-first ordering so multi-word keys ("room air", "gas out") win.
_ABBR_KEYS = sorted(ABBREVIATIONS.keys(), key=len, reverse=True)
_ABBR_PATTERN = re.compile(
    "|".join(re.escape(k) for k in _ABBR_KEYS)
)

_UNIT_KEYS = sorted(UNIT_READINGS.keys(), key=len, reverse=True)
_NUMBER_WITH_UNIT = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>" + "|".join(re.escape(u) for u in _UNIT_KEYS) + r")(?![A-Za-z])"
)
_NUMBER_WITH_COUNTER = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<counter>[가-힣]{1,2})"
)
_SLASH_PAIR = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")
_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[~\-–]\s*(\d+(?:\.\d+)?)")
_ARROW = re.compile(r"\s*(?:→|->)\s*")
_PLAIN_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_WORD_BOUNDARY_ABBR = re.compile(r"(?<![A-Za-z0-9])(" + _ABBR_PATTERN.pattern + r")(?![A-Za-z0-9])")


def _pick(options: list[str], rng: random.Random) -> str:
    return rng.choice(options) if len(options) > 1 else options[0]


def to_tts_text(spoken: str, rng: random.Random | None = None) -> str:
    """Convert a written nursing narrative into phonetic Korean for TTS."""
    rng = rng or random.Random()
    text = spoken

    # 0. thousands separators "1,800cc" -> "1800cc"
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)

    # 1. Arrows (37.4→36.9) read as "에서"
    text = _ARROW.sub(" 에서 ", text)

    # 2. "a/b" numeric pairs (BP, I/O) -> "a 에 b"
    text = _SLASH_PAIR.sub(lambda m: f"{m.group(1)} 에 {m.group(2)}", text)

    # 2b. chart-style vital chains "120/80-76-20-36.8": hyphens are separators, not ranges
    text = re.sub(r"(?<![\d.])(\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?){2,})(?![\d.])", lambda m: m.group(1).replace("-", ", "), text)

    # 3. ranges "150~180" -> "150 에서 180"
    text = _RANGE.sub(lambda m: f"{m.group(1)} 에서 {m.group(2)}", text)

    # 3-. "POD 3" / "POD#3" is said "피오디 삼일째" on this ward (not "피오디 삼")
    text = re.sub(r"(?<![A-Za-z])POD\s*#?\s*(\d+)(?![\d])", lambda m: f"피오디 {sino(int(m.group(1)))}일째", text)

    # 3a. any "q{n}h" not in the dictionary (q24h, q2h ...) -> "{n} 시간마다"
    text = re.sub(r"(?<![A-Za-z0-9])q\s*(\d+)\s*h(?![A-Za-z0-9])",  # \b fails before Hangul ("q24h이고")
                  lambda m: m.group(0) if m.group(0) in ABBREVIATIONS else f"{sino(int(m.group(1)))} 시간마다", text)

    # 3b. "<regimen> 항암" is also said "<regimen> 케모" on the ward
    text = re.sub(r"(?<=[A-Za-z0-9]) 항암(?![가-힣])", lambda m: _pick([" 항암", " 항암", " 케모"], rng), text)

    # 3c. months (6월 -> 유월, 10월 -> 시월)
    text = re.sub(r"(?<!\d)(1[0-2]|[1-9])월", lambda m: MONTH_READING[int(m.group(1))], text)

    # 4. numbers with units
    def unit_repl(m: re.Match) -> str:
        num = read_number(m.group("num"), None)
        unit = _pick(UNIT_READINGS[m.group("unit")], rng)
        return f"{num} {unit}".strip()

    text = _NUMBER_WITH_UNIT.sub(unit_repl, text)

    # 5. abbreviations and English vocabulary
    def abbr_repl(m: re.Match) -> str:
        return _pick(ABBREVIATIONS[m.group(1)], rng)

    text = _WORD_BOUNDARY_ABBR.sub(abbr_repl, text)

    # 5b. leftover Latin words, case-insensitively ("Mastectomy" -> "mastectomy", "Total" -> "total")
    text = re.sub(r"(?<![가-힣A-Za-z])([A-Za-z][A-Za-z-]*)(?![A-Za-z])",
                  lambda m: _pick(_ABBR_LOWER[m.group(1).lower()], rng) if m.group(1).lower() in _ABBR_LOWER else m.group(1),
                  text)

    # 5c. leftover "+" between items -> 플러스 (after abbreviations so "K+TC" is 키트루다 티씨, not 포타슘 플러스)
    text = re.sub(r"\s*\+\s*", " 플러스 ", text)

    # 6. numbers followed by Korean counters
    def counter_repl(m: re.Match) -> str:
        counter = m.group("counter")
        # Only the first syllable decides native vs sino ("시간", "개월" ...)
        key = counter if counter in NATIVE_COUNTERS or counter in SINO_COUNTERS else counter[0]
        num = read_number(m.group("num"), key)
        return f"{num} {counter}"

    text = _NUMBER_WITH_COUNTER.sub(counter_repl, text)

    # 7. remaining bare numbers -> sino
    text = _PLAIN_NUMBER.sub(lambda m: read_number(m.group(0)), text)

    # 8. leftover ALL-CAPS tokens -> spelled letters
    text = re.sub(r"(?<![가-힣A-Za-z])([A-Z]{1,6})(?![a-z])", lambda m: spell_letters(m.group(1)), text)  # incl. staging "T3"

    # 9. tidy whitespace and punctuation
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ,", ",", text)
    text = re.sub(r" \.", ".", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Dates and times (used by the signal line, so both layers are explicit)
# ---------------------------------------------------------------------------

MONTH_READING = {1: "일월", 2: "이월", 3: "삼월", 4: "사월", 5: "오월", 6: "유월", 7: "칠월",
                 8: "팔월", 9: "구월", 10: "시월", 11: "십일월", 12: "십이월"}


def read_date(year: int, month: int, day: int) -> str:
    return f"{sino(year)}년 {MONTH_READING[month]} {sino(day)}일"


def read_time(hour: int, minute: int, ampm: bool = True) -> str:
    """24h -> '오전 열 시 삼십 분'."""
    if ampm:
        prefix = "오전" if hour < 12 else "오후"
        h12 = hour % 12
        if h12 == 0:
            h12 = 12
        base = f"{prefix} {native(h12)} 시"
    else:
        base = f"{native(hour) if hour < 100 else sino(hour)} 시"
    if minute == 0:
        return base
    if minute == 30:
        # Nurses say both "삼십 분" and "반"
        return f"{base} 삼십 분"
    return f"{base} {sino(minute)} 분"


def written_time(hour: int, minute: int) -> str:
    prefix = "오전" if hour < 12 else "오후"
    h12 = hour % 12 or 12
    return f"{prefix} {h12}시 {minute}분" if minute else f"{prefix} {h12}시"


def written_date(year: int, month: int, day: int) -> str:
    return f"{year}년 {month}월 {day}일"


def temperature_casual(bt: float) -> str:
    """37.4 -> '7도 4' style written form (nurse slang)."""
    whole = int(bt)
    frac = round((bt - whole) * 10)
    last = whole % 10
    return f"{last}도 {frac}" if frac else f"{last}도"
