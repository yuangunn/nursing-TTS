"""간호 프로토콜(정규 차팅) 체크리스트.

Nursing-diagnosis based routine charting items.  Every protocol is a Section;
each intervention is a bool field whose phrases are written in the chart
register ("~함."); detail fields (site, score, drug...) are referenced from
the phrases as placeholders.  The style expander turns "~함." into
"~하였습니다." / "~했고요," / "~했어요." for the spoken styles, so the same
checklist serves chart-style and narrated recordings.

``protocol_sections(record_key)`` returns the subset relevant to a record
kind (s1..s6).  Field keys are prefixed with ``p_`` so they never collide
with the template's own fields.
"""
from __future__ import annotations

from .base import Field, Section, opt, sel, num, txt, boolean, multi

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _b(key: str, label: str, *phrases: str, default: bool = False, prob: float = 1.0) -> Field:
    return Field(key=f"p_{key}", label=label, kind="bool", phrases=list(phrases), default=default, speak_prob=prob)


def _t(key: str, label: str, placeholder: str, default: str = "") -> Field:
    # detail field: never spoken on its own, only via placeholders in item phrases
    return Field(key=f"p_{key}", label=label, kind="text", phrases=[], placeholder=placeholder, default=default or None, speak_prob=0.0)


def _n(key: str, label: str, default, mn, mx, step=1) -> Field:
    return Field(key=f"p_{key}", label=label, kind="number", phrases=[], default=default, min=mn, max=mx, step=step, speak_prob=0.0)


def _s(key: str, label: str, options: list, default: str) -> Field:
    # detail select whose *label* is substituted (phrases=[] so it is silent itself)
    return Field(key=f"p_{key}", label=label, kind="select", options=options, default=default, speak_prob=0.0,
                 skip_values=tuple(o.value for o in options))


# ---------------------------------------------------------------------------
# Protocol definitions
# ---------------------------------------------------------------------------

def routine() -> Section:
    return Section("prot_routine", "Routine check up", hint="수면·상태·식사 루틴 확인", fields=[
        _b("sleep_obs", "수면양상을 관찰함", "수면양상을 관찰함({p_sleep_note}).", "수면 양상 관찰함, {p_sleep_note}.", "밤 동안 {p_sleep_note}."),
        _t("sleep_note", "수면 상태", "예: 특이사항 없이 잘 잤다고 함", "특이사항 없이 잘 잤다고 함"),
        _b("status_check", "환자 상태 확인함", "환자 상태 확인함({p_status_note}).", "환자 상태 확인함, {p_status_note}.", "라운딩 시 {p_status_note}."),
        _s("status_note", "환자 상태", [
            opt("stable", "특별한 증상 호소 없이 안정 중임"), opt("chill", "오한 호소함"), opt("nausea", "오심 호소함"),
            opt("vomit", "구토 1회 있었음"), opt("dizzy", "어지러움 호소함"), opt("pain", "통증 호소함"),
        ], "stable"),
        _b("meal_check", "식사량 확인함", "식사량 확인함({p_meal_note}).", "식사 {p_meal_note}.", "식사량 확인함, {p_meal_note}."),
        _s("meal_note", "식사량", [opt("all", "전량 섭취함"), opt("half", "절반 정도 섭취함"), opt("third", "1/3 정도 섭취함"),
                                 opt("little", "소량만 섭취함, 식욕 저하 호소"), opt("npo", "금식 중임")], "all"),
        _b("vs_routine", "활력징후 측정함 (정규)", "정규 활력징후 측정함, 특이사항 없음.", "V/S 체크함, 정상 범위임.", "활력징후 측정함, 이상 소견 없음."),
    ])


def fall_high() -> Section:
    return Section("prot_fall_high", "낙상 예방 (낙상 고위험군)", hint="존스홉킨스 낙상 평가 14점 이상 고위험군", fields=[
        _b("fall_reassess", "낙상 위험도 재사정함", "낙상 위험도 재사정함, {p_jhfrat}점 고위험군.", "낙상 재사정 {p_jhfrat}점으로 고위험군 유지됨."),
        _b("fall_edu", "낙상 예방지침에 대해 교육함", "낙상 예방지침에 대해 교육함.", "환자와 보호자분께 낙상 예방지침 교육함.", "낙상 고위험군으로 낙상 예방 교육 시행함."),
        _b("fall_intervene", "낙상예방 중재함", "낙상예방 중재함({p_fall_items}).", "낙상 예방 위해 {p_fall_items}.", "{p_fall_items}."),
        multi("p_fall_items", "중재 항목", [
            opt("near", "자주 쓰는 물건을 침상 옆에 둠", nouns=["자주 쓰는 물건을 침상 옆에 둠"]),
            opt("low", "침상 높이를 낮춤", nouns=["침상 높이를 낮춤"]),
            opt("rail", "침상 난간 올려줌", nouns=["침상 난간 올려줌"]),
            opt("wheel", "침상 바퀴 고정 확인함", nouns=["침상 바퀴 고정 확인함"]),
            opt("light", "야간 조명 유지함", nouns=["야간 조명 유지함"]),
            opt("shoes", "미끄럼 방지 신발 착용 교육함", nouns=["미끄럼 방지 신발 착용 교육함"]),
        ], phrases=[], default=["near", "low", "rail", "wheel"], speak_prob=0.0),
        _b("call_bell", "call bell 제공함", "call bell 제공함.", "콜벨 손 닿는 곳에 두고 사용법 설명함.", "콜벨 제공하고 필요 시 호출하도록 교육함."),
        _b("fall_bracelet", "낙상 고위험 팔찌/표식 적용함", "낙상 고위험 팔찌 적용함.", "낙상 고위험 표식 부착함."),
        _n("jhfrat", "낙상 점수 (존스홉킨스)", 16, 0, 35, 1),
    ])


def fall_low() -> Section:
    return Section("prot_fall_low", "환경관리 (낙상 저위험군)", hint="저위험군 환경 중재", fields=[
        _b("env_intervene", "낙상예방 중재함", "낙상예방 중재함({p_env_items}).", "환경관리 시행함, {p_env_items}.", "{p_env_items}."),
        multi("p_env_items", "중재 항목", [
            opt("near", "자주 쓰는 물건을 침상 옆에 둠", nouns=["자주 쓰는 물건을 침상 옆에 둠"]),
            opt("low", "침상 높이를 낮춤", nouns=["침상 높이를 낮춤"]),
            opt("rail", "침상 난간 올려줌", nouns=["침상 난간 올려줌"]),
            opt("wheel", "침상 바퀴 고정 확인함", nouns=["침상 바퀴 고정 확인함"]),
            opt("floor", "바닥 물기·장애물 제거함", nouns=["바닥 물기와 장애물 제거함"]),
        ], phrases=[], default=["near", "low", "rail", "wheel"], speak_prob=0.0),
        _b("env_edu", "환경 안전 교육함", "병실 환경 안전에 대해 교육함.", "침상 주변 정리하고 안전 교육함."),
    ])


def _pain(prefix: str, title: str, hint: str, acute: bool) -> Section:
    fields = [
        _b(f"{prefix}_assess", "통증을 사정함", "통증을 사정함({p_%s_site}, {p_%s_scale} {p_%s_score}점, {p_%s_char}, {p_%s_duration})." % ((prefix,) * 5),
           "{p_%s_site} 통증 {p_%s_scale} {p_%s_score}점으로 사정함, {p_%s_char} 양상, {p_%s_duration}." % ((prefix,) * 5),
           "{p_%s_site}에 {p_%s_char} 통증 호소함, {p_%s_scale} {p_%s_score}점." % ((prefix,) * 4)),
        _t(f"{prefix}_site", "부위", "예: 수술 부위 복부", "수술 부위" if acute else "허리"),
        _s(f"{prefix}_scale", "척도", [opt("NRS", "NRS"), opt("VAS", "VAS"), opt("PAINAD", "PAINAD"), opt("FLACC", "FLACC")], "NRS"),   # 성인 병동: NRS가 기본
        _n(f"{prefix}_score", "정도 (0~10)", 3 if acute else 4, 0, 10),
        _s(f"{prefix}_char", "통증 양상", [opt("쑤시는", "쑤시는"), opt("찌르는", "찌르는"), opt("당기는", "당기는"), opt("욱신거리는", "욱신거리는"),
                                      opt("둔한", "둔한"), opt("타는 듯한", "타는 듯한"), opt("쥐어짜는", "쥐어짜는"), opt("저린", "저린")], "쑤시는" if acute else "둔한"),
        _t(f"{prefix}_duration", "지속기간", "예: 간헐적, 움직일 때 심해짐", "간헐적, 움직일 때 심해짐" if acute else "지속적"),
        _b(f"{prefix}_intervene", "통증을 중재함", "통증을 중재함({p_%s_drug} {p_%s_route})." % (prefix, prefix),
           "{p_%s_drug} {p_%s_route} 투여함." % (prefix, prefix), "처방에 따라 {p_%s_drug} {p_%s_route}로 투여하고 반응 관찰함." % (prefix, prefix)),
        _t(f"{prefix}_drug", "처방명", "예: 트라마돌 50mg", "트라마돌 50mg" if acute else "아세트아미노펜 650mg"),
        _s(f"{prefix}_route", "투여경로", [opt("IV", "IV"), opt("PO", "PO"), opt("IM", "IM"), opt("SC", "SC"), opt("PCA", "PCA")], "IV" if acute else "PO"),
        _b(f"{prefix}_nonpharm", "비약물적 중재함", "비약물적 중재함({p_%s_nonpharm_note})." % prefix, "{p_%s_nonpharm_note}." % prefix),
        _s(f"{prefix}_nonpharm_note", "비약물 중재", [opt("체위 변경함", "체위 변경함"), opt("ice pack 적용함", "ice pack 적용함"), opt("온찜질 적용함", "온찜질 적용함"),
                                                opt("이완요법과 심호흡 교육함", "이완요법과 심호흡 교육함"), opt("주의 전환 시행함", "주의 전환 시행함")], "체위 변경함"),
        _b(f"{prefix}_edu", "통증에 대한 정보를 제공함", "통증에 대한 정보를 제공함(통증 심해지기 전에 진통제 사용할 것을 교육함).",
           "통증 심해지기 전에 진통제 요구하도록 교육함.", "통증 사정 척도와 진통제 사용 시점에 대해 교육함."),
        _b(f"{prefix}_reassess", "중재 후 통증 재사정함", "중재 후 통증 재사정함, {p_%s_scale} {p_%s_re_score}점." % (prefix, prefix),
           "30분 후 통증 재사정함, {p_%s_re_score}점으로 감소함." % prefix, "진통제 투여 후 통증 {p_%s_re_score}점으로 호전됨." % prefix),
        _n(f"{prefix}_re_score", "재사정 점수", 1 if acute else 2, 0, 10),
    ]
    if acute:
        fields += [
            _b("pca_check", "IV PCA 확인함", "IV PCA 확인함({p_pca_note}).", "PCA 잔량과 주입 상태 확인함, {p_pca_note}.", "PCA 버튼 사용법 재교육하고 잔량 확인함."),
            _s("pca_note", "PCA 상태", [opt("잘 주입되고 있음", "잘 주입되고 있음"), opt("잔량 절반 남음", "잔량 절반 남음"), opt("오심 호소 없음", "오심 호소 없음"),
                                     opt("버튼 사용법 이해함", "버튼 사용법 이해함"), opt("오심 호소하여 주입속도 조절함", "오심 호소하여 주입속도 조절함")], "잘 주입되고 있음"),
            _b("pca_end", "IV PCA 종료함", "IV PCA 종료함(전량 주입됨, 리필 원하지 않음).", "PCA 전량 주입되어 제거함. 리필 원하지 않음.", "PCA 종료하고 경구 진통제로 전환함."),
        ]
    return Section(f"prot_{prefix}", title, hint=hint, fields=fields)


def pain_acute() -> Section:
    return _pain("apain", "급성통증 (수술·상처·삽입·시술·검사·자극부위)", "부위, 정도, 척도, 양상, 지속기간 → 중재 → 교육 → PCA", True)


def pain_chronic() -> Section:
    return _pain("cpain", "만성통증 (자극부위)", "만성 통증 사정·중재·교육", False)


def wound() -> Section:
    return Section("prot_wound", "Wound care", hint="상처 관찰, 드레싱 상태, 드레싱 시행", fields=[
        _b("wound_obs", "상처를 관찰함", "상처를 관찰함({p_wound_site}, {p_wound_state}).", "{p_wound_site} 상처 {p_wound_state}.", "{p_wound_site} 관찰함, {p_wound_state}."),
        _t("wound_site", "부위", "예: 복부 수술 부위", "복부 수술 부위"),
        _s("wound_state", "상태", [opt("clean", "발적·부종·삼출물 없이 깨끗함"), opt("dry", "건조하고 치유 양호함"), opt("red", "경미한 발적 있음"),
                                  opt("ooze", "소량 장액성 삼출물 있음"), opt("bleed", "소량 출혈 있음"), opt("dehis", "봉합 부위 벌어짐 의심되어 주치의 노티함")], "clean"),
        _b("dressing_check", "Dressing 상태를 확인함", "Dressing 상태를 확인함({p_dsg_site}, {p_dsg_state}).", "{p_dsg_site} 드레싱 {p_dsg_state}.", "드레싱 {p_dsg_state} 확인함."),
        _t("dsg_site", "드레싱 부위", "예: 복부", "복부"),
        _s("dsg_state", "드레싱 상태", [opt("clean", "깨끗하고 건조함"), opt("intact", "고정 양호함"), opt("wet", "소량 젖어 있음"), opt("blood", "혈액 비침 소량 있음"), opt("off", "일부 떨어져 보강함")], "clean"),
        _b("dressing_do", "상처 Dressing함", "상처 Dressing함({p_dsg_site2}, 시행자 {p_dsg_by}).", "{p_dsg_by}(이)가 {p_dsg_site2} 드레싱 교환함.", "{p_dsg_by} {p_dsg_site2} 소독 및 드레싱 시행함."),
        _t("dsg_site2", "시행 부위", "예: 복부 수술 부위", "복부 수술 부위"),
        _s("dsg_by", "시행자", [opt("주치의", "주치의"), opt("담당 간호사", "담당 간호사"), opt("외과 전공의", "외과 전공의"), opt("상처 전문 간호사", "상처 전문 간호사")], "주치의"),
        _b("wound_edu", "상처 관리 교육함", "상처 관리 교육함(드레싱 젖거나 출혈 시 알리도록).", "상처 부위 청결 유지와 이상 증상 시 알리도록 교육함."),
    ])


def medication() -> Section:
    return Section("prot_med", "약물투여", hint="주입속도, 주사부위, 약물 교육, 부작용", fields=[
        _b("inf_rate", "주입속도를 확인함", "주입속도를 확인함({p_inf_note}).", "{p_inf_note} 주입 속도 확인함.", "수액 {p_inf_note}로 잘 들어가고 있음 확인함."),
        _t("inf_note", "수액/속도", "예: 하트만 1L 40cc/hr", "하트만 1L 40cc/hr"),
        _b("iv_site_check", "주사부위를 확인함", "주사부위를 확인함({p_iv_gauge} {p_iv_site}, Dressing {p_iv_dsg}, patency {p_iv_patency}).",
           "{p_iv_site} {p_iv_gauge} IV line 확인함, 드레싱 {p_iv_dsg}, 개방성 {p_iv_patency}.", "IV site {p_iv_site} 발적·부종 없고 {p_iv_patency}."),
        _s("iv_gauge", "IV line Gauge", [opt("18G", "18G"), opt("20G", "20G"), opt("22G", "22G"), opt("24G", "24G")], "22G"),
        _t("iv_site", "부위", "예: Lt arm, Rt hand", "Lt arm"),
        _s("iv_dsg", "Dressing 상태", [opt("깨끗함", "깨끗함"), opt("고정 양호함", "고정 양호함"), opt("젖어 교환함", "젖어 교환함"), opt("들떠 재고정함", "들떠 재고정함")], "깨끗함"),
        _s("iv_patency", "patency", [opt("양호함", "양호함"), opt("혈액 역류 확인됨", "혈액 역류 확인됨"), opt("불량하여 재삽입함", "불량하여 재삽입함")], "양호함"),
        _b("med_edu", "약물에 대해 교육함", "약물에 대해 교육함({p_med_name}: 효능, 투여 방법, 주의사항).", "{p_med_name} 효능과 부작용에 대해 교육함.", "투여 약물 {p_med_name}에 대해 설명하고 이해 여부 확인함."),
        _t("med_name", "약물명", "예: 세파졸린 1g", "세파졸린 1g"),
        _b("med_side", "투여한 약물 부작용 사정함", "투여한 약물 부작용 사정함({p_med_side_note}).", "{p_med_name} 투여 후 부작용 사정함, {p_med_side_note}.", "약물 부작용 {p_med_side_note}."),
        _s("med_side_note", "부작용", [opt("특이 반응 없음", "특이 반응 없음"), opt("오심 호소하여 관찰 중", "오심 호소하여 관찰 중"), opt("발진 없음", "발진 없음"),
                                    opt("어지러움 호소함", "어지러움 호소함"), opt("주사 부위 통증 호소함", "주사 부위 통증 호소함")], "특이 반응 없음"),
        _b("med_given", "처방 약물 투여함", "처방대로 {p_med_name} 투여함.", "{p_med_name} 정시 투여함.", "5 rights 확인 후 {p_med_name} 투여함."),
        _b("ast", "항생제 피부반응검사 시행함", "항생제 피부반응검사 시행함, 음성.", "AST 시행하고 15분 후 음성 확인함."),
    ])


def breathing() -> Section:
    return Section("prot_breath", "비효율적 호흡양상", hint="호흡 사정, 산소, 심호흡·기침, 폐활량계, 체위", fields=[
        _b("resp_assess", "호흡양상을 사정함", "호흡양상을 사정함(호흡수 {p_rr}회, SpO2 {p_spo2}%, 호흡음 {p_breath_sound}).",
           "호흡 {p_rr}회, SpO2 {p_spo2}% 측정됨, 호흡음 {p_breath_sound}.", "호흡 양상 사정함, {p_breath_sound}, 호흡보조근 사용 {p_accessory}."),
        _n("rr", "호흡수", 18, 8, 40), _n("spo2", "SpO2", 97, 70, 100),
        _s("breath_sound", "호흡음", [opt("양측 깨끗함", "양측 깨끗함"), opt("하부 감소됨", "하부 감소됨"), opt("수포음 들림", "수포음 들림"), opt("천명음 들림", "천명음 들림")], "양측 깨끗함"),
        _s("accessory", "호흡보조근 사용", [opt("없음", "없음"), opt("있음", "있음")], "없음"),
        _b("o2_apply", "산소 적용함", "산소 적용함({p_o2_method} {p_o2_flow}L/min).", "{p_o2_method} {p_o2_flow}L로 산소 투여하고 SpO2 관찰함.", "SpO2 저하되어 {p_o2_method} {p_o2_flow}L 산소 적용함."),
        _s("o2_method", "산소 방법", [opt("nasal cannula", "nasal cannula"), opt("simple mask", "simple mask"), opt("reservoir mask", "reservoir mask"), opt("high flow", "high flow")], "nasal cannula"),
        _n("o2_flow", "유량 (L/min)", 3, 1, 15),
        _b("deep_breath", "심호흡·기침 교육함", "심호흡과 기침을 교육함.", "무기폐 예방 위해 심호흡·기침 교육하고 시행 확인함.", "심호흡 자주 하도록 격려함."),
        _b("spirometer", "강화폐활량계 시행 격려함", "강화폐활량계 시행 격려함(시간당 {p_spiro_count}회, 공 {p_spiro_ball}개).", "inspirometer 시간당 {p_spiro_count}회 시행하도록 격려하고 직접 시행 확인함.",
           "강화폐활량계 공 {p_spiro_ball}개 올리는 것 확인함."),
        _n("spiro_count", "시간당 횟수", 10, 1, 30), _n("spiro_ball", "공 개수", 3, 1, 3),
        _b("position", "체위 변경함 (반좌위)", "호흡 편하도록 반좌위 취해 줌.", "침상 머리 30~45도 올려 체위 변경함.", "반좌위 유지하도록 함."),
        _b("sputum", "객담 배출 격려함/네뷸라이저 적용함", "객담 배출 격려함.", "네뷸라이저 적용하고 객담 배출 격려함.", "처방에 따라 네뷸라이저 적용함, 객담 배출 양호함."),
        _b("dyspnea_edu", "호흡곤란 시 즉시 알리도록 교육함", "호흡곤란이나 숨참 시 즉시 알리도록 교육함.", "숨차거나 가슴 답답하면 바로 호출하도록 교육함."),
    ])


def drain() -> Section:
    return Section("prot_drain", "배액관 관리", hint="종류·부위·삽입일, 양상·양, 고정, 교육, 제거", fields=[
        _b("drain_check", "배액관 상태 확인함", "배액관 상태 확인함({p_drain_type}, {p_drain_site}, 삽입일 {p_drain_date}).", "{p_drain_site} {p_drain_type} 유지 중, 삽입일 {p_drain_date}.", "{p_drain_type} 유지 상태 확인함."),
        _s("drain_type", "종류", [opt("JP", "JP"), opt("Hemovac", "Hemovac"), opt("PCD", "PCD"), opt("PTBD", "PTBD"), opt("chest tube", "chest tube"), opt("Penrose", "Penrose")], "JP"),
        _t("drain_site", "부위", "예: 우측 복부", "우측 복부"), _t("drain_date", "삽입일", "예: 10월 14일", "10월 14일"),
        _b("drain_output", "배액 양상·양 확인함", "배액 양상·양 확인함({p_drain_color} {p_drain_amount}cc).", "배액 {p_drain_color} 양상으로 {p_drain_amount}cc 배액됨.", "{p_drain_type} {p_drain_amount}cc, {p_drain_color}."),
        _s("drain_color", "양상", [opt("bloody", "bloody"), opt("serosanguineous", "serosanguineous"), opt("serous", "serous"), opt("bilious", "bilious"), opt("purulent", "purulent")], "serosanguineous"),
        _n("drain_amount", "양 (cc)", 40, 0, 2000, 5),
        _b("drain_fix", "배액관 고정 상태 확인함 / milking 시행함", "배액관 고정 상태 확인하고 milking 시행함.", "배액관 꺾임·당김 없이 고정 양호함, milking 함.", "배액관 개방성 확인하고 음압 유지함."),
        _b("drain_edu", "배액관 관리 교육함", "배액관 관리 교육함(당겨지지 않도록 주의, 비우는 방법, 양상 변화 시 알리기).", "배액관 당겨지지 않도록 주의하고 혈액색 짙어지거나 양 늘면 알리도록 교육함."),
        _b("drain_remove", "배액관 제거함", "배액관 제거함(시행자 {p_drain_by}), 제거 부위 드레싱함.", "{p_drain_by} {p_drain_type} 제거함, 제거 부위 출혈 없음.", "{p_drain_type} 제거 후 부위 드레싱하고 관찰 중."),
        _s("drain_by", "시행자", [opt("주치의", "주치의"), opt("외과 전공의", "외과 전공의")], "주치의"),
    ])


def catheter() -> Section:
    return Section("prot_foley", "도뇨관 관리", hint="종류·크기, 소변 양상·양, 고정, 회음부 간호, 제거·자가배뇨", fields=[
        _b("foley_check", "도뇨관 유지 상태 확인함", "도뇨관 유지 상태 확인함({p_foley_type} {p_foley_size}, 삽입일 {p_foley_date}).", "{p_foley_type} {p_foley_size} 유지 중, 삽입일 {p_foley_date}.", "도뇨관 개방성 확인함."),
        _s("foley_type", "종류", [opt("Foley catheter", "Foley catheter"), opt("Nelaton (간헐적)", "Nelaton"), opt("Suprapubic", "Suprapubic")], "Foley catheter"),
        _s("foley_size", "크기", [opt("14Fr", "14Fr"), opt("16Fr", "16Fr"), opt("18Fr", "18Fr")], "16Fr"),
        _t("foley_date", "삽입일", "예: 10월 14일", "10월 14일"),
        _b("urine_check", "소변 양상·양 확인함", "소변 양상·양 확인함, {p_urine_color} {p_urine_amount}cc.", "소변 {p_urine_color} {p_urine_amount}cc 배출됨.", "소변 {p_urine_color} 나오고 {p_urine_amount}cc 확인함."),
        _s("urine_color", "양상", [opt("straw하게", "straw하게"), opt("orange 색깔로", "orange 색깔로"), opt("pinkish하게", "pinkish하게"), opt("turbid하게", "turbid하게")], "straw하게"),   # 색 straw·orange·pinkish, 탁도 turbid (user 2026-10-18)
        _n("urine_amount", "양 (cc)", 400, 0, 5000, 50),
        _b("foley_fix", "도뇨관 고정·소변백 위치 확인함", "도뇨관 고정하고 소변백 방광 아래 위치 유지함.", "소변줄 꼬임 없이 고정 양호하고 소변백 바닥에 닿지 않게 유지함."),
        _b("peri_care", "회음부 간호 시행함", "회음부 간호 시행함.", "도뇨관 삽입 부위 청결 유지 위해 회음부 간호함."),
        _b("foley_remove", "도뇨관 제거함", "도뇨관 제거함({p_foley_by}), 제거 후 자가배뇨 확인 예정.", "{p_foley_by} 도뇨관 제거함, 불편감 없음."),
        _s("foley_by", "시행자", [opt("담당 간호사", "담당 간호사"), opt("주치의", "주치의")], "담당 간호사"),
        _b("self_void", "제거 후 자가배뇨 확인함", "제거 후 자가배뇨 확인함({p_void_time}, {p_void_amount}cc).", "제거 {p_void_time} 후 자가배뇨 {p_void_amount}cc 확인함.", "self voiding 잘 되고 잔뇨감 없음."),
        _t("void_time", "경과 시간", "예: 4시간", "4시간"), _n("void_amount", "배뇨량 (cc)", 250, 0, 2000, 10),
        _b("residual_check", "잔뇨 확인함 (방광 스캔)", "방광 스캔으로 잔뇨 확인함, {p_residual}cc.", "잔뇨 {p_residual}cc로 확인됨."),
        _n("residual", "잔뇨 (cc)", 30, 0, 1000, 10),
    ])


def fever() -> Section:
    return Section("prot_fever", "고체온", hint="체온, 원인 사정, 해열제, 물리적 중재, 재측정, 노티, 배양", fields=[
        _b("temp_measure", "체온 측정함", "체온 측정함({p_temp}도, {p_temp_site}).", "BT {p_temp}도 측정됨({p_temp_site}).", "{p_temp_site} 체온 {p_temp}도로 발열 확인됨."),
        _n("temp", "체온", 38.2, 35.0, 42.0, 0.1),
        _s("temp_site", "측정 부위", [opt("고막", "고막"), opt("액와", "액와"), opt("구강", "구강"), opt("이마", "이마")], "고막"),
        _b("fever_assess", "발열 원인 사정함", "발열 원인 사정함({p_fever_sx}).", "발열 관련 증상 사정함, {p_fever_sx}.", "오한, 호흡기, 요로 증상 사정함, {p_fever_sx}."),   # 항암 환자에게 "수술 부위" (2026-10-18)
        _s("fever_sx", "동반 증상", [opt("오한 없음", "오한 없음, 수술 부위 발적 없음"), opt("오한 있음", "오한 동반함"), opt("기침·객담", "기침과 객담 있음"), opt("배뇨통", "배뇨 시 통증 있음"),
                                   opt("수술 부위 발적", "수술 부위 발적·열감 있음"), opt("특이 증상 없음", "특이 증상 없음")], "오한 없음"),
        _b("fever_noti", "주치의 노티함", "발열 주치의 노티함.", "BT {p_temp}도 주치의 노티하고 처방 확인함."),
        _b("culture_do", "배양 검사 시행함", "배양 검사 시행함({p_culture}).", "{p_culture} 검체 채취하여 검사실 보냄."),
        _s("culture", "검체", [opt("blood culture 2쌍", "blood culture 2쌍"), opt("urine culture", "urine culture"), opt("sputum culture", "sputum culture"), opt("wound culture", "wound culture")], "blood culture 2쌍"),
        _b("antipyretic_give", "해열제 투여함", "해열제 투여함({p_antipyretic} {p_antipyretic_route}).", "{p_antipyretic} {p_antipyretic_route} 투여함.", "처방에 따라 {p_antipyretic} {p_antipyretic_route} 투여함."),
        _t("antipyretic", "약명", "예: acetaminophen 1g", "acetaminophen 1g"),
        _s("antipyretic_route", "경로", [opt("IV", "IV"), opt("PO", "PO")], "IV"),
        _b("tepid", "미온수 마사지/ice pack 적용함", "미온수 마사지 적용함.", "ice pack 적용하고 얇은 이불로 교체함.", "미온수 마사지 시행하고 보온 조절함."),
        _b("fluid_encourage", "수분 섭취 격려함", "수분 섭취 격려함.", "탈수 예방 위해 수분 섭취 격려함."),
        _b("temp_recheck", "체온 재측정함", "체온 재측정함({p_recheck_time}, {p_recheck_temp}도).", "{p_recheck_time} 재측정 BT {p_recheck_temp}도로 하강함.", "해열제 투여 {p_recheck_time} {p_recheck_temp}도 확인됨."),
        _t("recheck_time", "재측정 시각", "예: 1시간 후", "1시간 후"), _n("recheck_temp", "재측정 체온", 37.3, 35.0, 42.0, 0.1),
    ])


def nausea() -> Section:
    return Section("prot_nausea", "오심", hint="사정, 항구토제, 식이 조절, 구강 간호, 체위, 재사정", fields=[
        _b("nausea_assess", "오심/구토 사정함", "오심/구토 사정함({p_nv_note}).", "오심 호소함, {p_nv_note}.", "오심·구토 양상 사정함, {p_nv_note}."),
        _s("nv_note", "양상", [opt("오심만 있고 구토 없음", "오심만 있고 구토 없음"), opt("구토 1회", "구토 1회, 소화된 음식물"), opt("구토 2회 이상", "구토 2회 이상"),
                               opt("식후 오심", "식후에 심해짐"), opt("PCA 관련 오심", "PCA 관련 오심 의심")], "오심만 있고 구토 없음"),
        _b("antiemetic_give", "항구토제 투여함", "항구토제 투여함({p_antiemetic} {p_antiemetic_route}).", "{p_antiemetic} {p_antiemetic_route} 투여함.", "처방에 따라 {p_antiemetic} 투여하고 반응 관찰함."),
        _t("antiemetic", "약명", "예: 메토클로프라미드 10mg", "메토클로프라미드 10mg"),
        _s("antiemetic_route", "경로", [opt("IV", "IV"), opt("PO", "PO"), opt("IM", "IM")], "IV"),
        _b("diet_adjust", "금식/소량 식이 조절함", "소량씩 자주 섭취하도록 식이 조절함.", "오심 호전될 때까지 식사 보류함."),
        _b("oral_care", "구강 간호 시행함", "구강 간호 시행함.", "구강 헹굼 돕고 구강 간호함."),
        _b("nv_position", "체위 조정함", "흡인 예방 위해 머리 올리고 측위 유지함.", "침상 머리 올려 편안한 체위 취해 줌."),
        _b("nv_edu", "구토 시 흡인 예방 교육함", "구토 시 고개 옆으로 돌리도록 흡인 예방 교육함.", "구토 시 즉시 알리고 고개 옆으로 돌리도록 교육함."),
        _b("nv_reassess", "재사정함", "중재 후 오심 재사정함, {p_nv_re}.", "항구토제 투여 후 {p_nv_re}."),
        _s("nv_re", "재사정 결과", [opt("오심 호전됨", "오심 호전됨"), opt("오심 지속되어 주치의 노티함", "오심 지속되어 주치의 노티함"), opt("구토 없음", "구토 없이 안정됨")], "오심 호전됨"),
    ])


def glucose() -> Section:
    return Section("prot_glucose", "불안정한 혈당 수치 관리", hint="혈당 측정, 증상 사정, 인슐린, 저혈당 중재, 교육, 노티, 재측정", fields=[
        _b("bst", "혈당 측정함", "혈당 측정함({p_bst_time} {p_bst_value}mg/dL).", "BST {p_bst_time} {p_bst_value}mg/dL 측정됨.", "{p_bst_time} 혈당 {p_bst_value} 확인함."),
        _s("bst_time", "시점", [opt("아침 식전", "아침 식전"), opt("점심 식전", "점심 식전"), opt("저녁 식전", "저녁 식전"), opt("취침 전", "취침 전"), opt("식후 2시간", "식후 2시간"), opt("새벽 3시", "새벽 3시")], "아침 식전"),
        _n("bst_value", "혈당 (mg/dL)", 165, 30, 600, 1),
        _b("glucose_sx_check", "저/고혈당 증상 사정함", "저/고혈당 증상 사정함({p_glucose_sx}).", "저혈당·고혈당 증상 사정함, {p_glucose_sx}."),
        _s("glucose_sx", "증상", [opt("증상 없음", "증상 없음"), opt("식은땀·어지러움", "식은땀, 어지러움 호소함"), opt("손떨림", "손떨림 있음"), opt("갈증·다뇨", "갈증, 다뇨 호소함"), opt("의식 변화 없음", "의식 변화 없음")], "증상 없음"),
        _b("insulin_give", "인슐린 투여함", "인슐린 투여함({p_insulin} {p_insulin_unit}단위 {p_insulin_scheme}).", "{p_insulin_scheme}에 따라 {p_insulin} {p_insulin_unit}단위 SC 투여함.", "{p_insulin} {p_insulin_unit}단위 투여함."),
        _t("insulin", "종류", "예: RI", "RI"), _n("insulin_unit", "단위", 4, 0, 100, 1),
        _s("insulin_scheme", "방식", [opt("sliding scale", "sliding scale"), opt("정규 처방", "정규 처방"), opt("추가 처방", "추가 처방")], "sliding scale"),
        _b("hypo_intervene", "저혈당 중재함", "저혈당 중재함(당 공급 15g 후 15분 뒤 재측정).", "주스 섭취시키고 15분 후 혈당 재측정함.", "저혈당으로 50% DW 투여함, 주치의 노티."),
        _b("glucose_edu", "식이 조절 교육함", "당뇨 식이와 혈당 관리에 대해 교육함.", "규칙적인 식사와 저혈당 증상 시 대처법 교육함."),
        _b("glucose_noti", "주치의 노티함", "혈당 {p_bst_value}mg/dL 주치의 노티함.", "혈당 이상으로 주치의 노티하고 처방 확인함."),
        _b("bst_recheck", "혈당 재측정함", "혈당 재측정함({p_bst_re}mg/dL).", "재측정 혈당 {p_bst_re}mg/dL로 확인됨.", "중재 후 혈당 {p_bst_re}로 안정됨."),
        _n("bst_re", "재측정 혈당", 140, 30, 600, 1),
    ])


def pressure_injury() -> Section:
    return Section("prot_skin", "피부 통합성 장애 위험 (욕창 예방)", hint="Braden, 체위변경, 피부 사정, 압력 완화", fields=[
        _b("braden_check", "욕창 위험도 사정함", "욕창 위험도 사정함, {p_braden}점 {p_braden_risk}.", "욕창 {p_braden}점으로 {p_braden_risk} 확인함."),
        _n("braden", "욕창 점수 (Braden)", 18, 6, 23, 1),
        _s("braden_risk", "위험도", [opt("위험 없음", "위험 없음"), opt("저위험", "저위험"), opt("중등도 위험", "중등도 위험"), opt("고위험", "고위험"), opt("최고위험", "최고위험")], "저위험"),
        _b("skin_assess", "피부 상태 사정함", "피부 상태 사정함({p_skin_note}).", "천골·발뒤꿈치 등 압박 부위 피부 사정함, {p_skin_note}."),
        _s("skin_note", "피부 상태", [opt("발적 없음", "발적 없음"), opt("천골 부위 발적 있음", "천골 부위 발적 있음"), opt("피부 건조함", "피부 건조하여 보습제 적용함")], "발적 없음"),
        _b("reposition", "체위 변경함", "2시간마다 체위 변경함.", "체위 변경 시행하고 압박 부위 확인함."),
        _b("pressure_relief", "압력 완화 기구 적용함", "에어매트리스 적용함.", "발뒤꿈치 압력 완화 위해 베개 적용함."),
        _b("skin_edu", "피부 관리 교육함", "피부 청결·보습과 체위 변경 필요성 교육함.", "욕창 예방 교육함."),
    ])


def anxiety() -> Section:
    return Section("prot_anxiety", "불안 (수술·검사·질병 관련)", hint="불안 사정, 정보 제공, 정서적 지지", fields=[
        _b("anx_assess", "불안 정도 사정함", "불안 정도 사정함({p_anx_note}).", "{p_anx_note}."),
        _s("anx_note", "불안 양상", [opt("수술 관련 불안 호소함", "수술 관련 불안 호소함"), opt("검사 결과에 대해 걱정 표현함", "검사 결과에 대해 걱정 표현함"), opt("불안 호소 없음", "불안 호소 없음"),
                                   opt("통증에 대한 두려움 표현함", "통증에 대한 두려움 표현함")], "수술 관련 불안 호소함"),
        _b("anx_info", "정보 제공함", "수술 과정과 경과에 대해 설명하여 불안 완화함.", "궁금한 점 질문하도록 하고 충분히 설명함."),
        _b("anx_support", "정서적 지지함", "정서적 지지 제공함, 표정 편안해짐.", "경청하고 격려하여 정서적 지지함."),
        _b("anx_relax", "이완요법 교육함", "심호흡·이완요법 교육함.", "불안 시 심호흡하도록 교육함."),
    ])


# ---------------------------------------------------------------------------
# Record-kind mapping
# ---------------------------------------------------------------------------

_BUILDERS = {
    "routine": routine, "fall_high": fall_high, "fall_low": fall_low, "pain_acute": pain_acute, "pain_chronic": pain_chronic,
    "wound": wound, "medication": medication, "breathing": breathing, "drain": drain, "catheter": catheter, "fever": fever,
    "nausea": nausea, "glucose": glucose, "skin": pressure_injury, "anxiety": anxiety,
}

BY_RECORD: dict[str, list[str]] = {
    # 2026-10-17: the charting checklist belongs to the routine progress record only.  Education records (S1·S2·S3-1·S4),
    # the event record (S3-2, which already narrates 사정→노티→중재→재사정) and the spoken handover (S5) read like one
    # narrative; "~함" checklist items mixed into them produced contradictions (PCA 종료 on a PCA patient, 발열 노티
    # without fever, 낙상 재사정 17점 for a walking 34-year-old).
    "s1": [], "s2": [], "s3_1": [], "s3_2": [], "s4": [], "s5": [],
    "s6": ["routine", "fall_high", "fall_low", "pain_acute", "wound", "medication", "breathing", "drain", "catheter", "fever", "nausea", "glucose", "skin"],
}


def protocol_sections(record_key: str) -> list[Section]:
    out = []
    for name in BY_RECORD.get(record_key, []):
        sec = _BUILDERS[name]()
        sec.group = "protocol"
        out.append(sec)
    return out


def catalogue() -> list[dict]:
    return [{"key": k, "title": _BUILDERS[k]().title, "records": [r for r, lst in BY_RECORD.items() if k in lst]} for k in _BUILDERS]
