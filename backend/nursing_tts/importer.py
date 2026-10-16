"""Scripts from an external table (CSV/XLSX): parse the file, then apply a user-defined mapping
(which column feeds which patient/form field, and what each cell value means) to build generation specs.

The mapping is defined in the app and stored per template (``data_dir/import_mappings.json``)::

    {"columns": {"patient.name": "환자명", "patient.age": "나이", "datetime": "기록일시", "form.diet_edu": "식이"},
     "values":  {"form.diet_edu": {"일반식": "gd", "죽": "sd_small"}, "patient.sex": {"M": "남", "F": "여"}},
     "fixed":   {"patient.department": "외과", "style": "formal"}}
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Any

from .config import data_dir
from .templates import default_form, get_template

PATIENT_FIELDS = ["name", "age", "sex", "diagnosis", "surgery", "professor", "department", "pod", "op_date",
                  "admission_date", "kind", "regimen", "cycle", "day"]
PATIENT_LABELS = {"name": "환자 성명", "age": "나이", "sex": "성별", "diagnosis": "진단명", "surgery": "수술명", "professor": "담당 교수",
                  "department": "진료과", "pod": "POD", "op_date": "수술일/투여일", "admission_date": "입원일", "kind": "입원 종류(op/chemo)",
                  "regimen": "항암 regimen", "cycle": "항암 차수", "day": "항암 일차"}
_INT_FIELDS = {"age", "pod", "cycle", "day"}
_TRUE = {"y", "yes", "true", "1", "o", "예", "네", "있음", "함", "시행", "✓", "v", "t"}
_FALSE = {"n", "no", "false", "0", "x", "아니오", "없음", "안함", "미시행", "f", ""}


def parse_table(data: bytes, filename: str) -> dict[str, Any]:
    """CSV (UTF-8/CP949, any common delimiter) or XLSX (first sheet) -> columns, rows (strings), distinct values."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ValueError("엑셀(xlsx)을 읽으려면 백엔드에 openpyxl이 필요합니다. CSV로 저장해 올리거나 pip install openpyxl") from e
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        it = wb.active.iter_rows(values_only=True)
        header = [("" if c is None else str(c).strip()) for c in next(it, [])]
        rows = [{h: ("" if v is None else str(v).strip()) for h, v in zip(header, r) if h} for r in it]
    else:
        text = None
        for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-16"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("문자 인코딩을 알 수 없습니다. UTF-8 또는 CP949(엑셀 기본)로 저장하세요.")
        try:
            dialect: Any = csv.Sniffer().sniff(text[:4096], delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        header = [(h or "").strip() for h in (reader.fieldnames or [])]
        rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items() if (k or "").strip()} for r in reader]
    rows = [r for r in rows if any(r.values())]
    columns = [h for h in header if h]
    distinct = {h: sorted({r.get(h, "") for r in rows if r.get(h, "")})[:60] for h in columns}
    return {"columns": columns, "rows": rows, "count": len(rows), "distinct": distinct}


def targets_for(template_key: str) -> list[dict[str, Any]]:
    """Everything a column can feed: patient fields, the record datetime, and the template's form fields."""
    out = [{"key": f"patient.{k}", "label": PATIENT_LABELS[k], "kind": "number" if k in _INT_FIELDS else "text", "options": []}
           for k in PATIENT_FIELDS]
    out[2]["kind"], out[2]["options"] = "select", [{"value": "남", "label": "남"}, {"value": "여", "label": "여"}]
    out.append({"key": "datetime", "label": "기록 일시", "kind": "datetime", "options": []})
    t = get_template(template_key)
    for sec in t.sections:
        for f in sec.fields:
            if f.kind == "vitals":
                continue
            out.append({"key": f"form.{f.key}", "label": f"{sec.title} · {f.label}", "kind": f.kind,
                        "options": [{"value": o.value, "label": o.label} for o in getattr(f, "options", [])]})
    return out


def _to_int(v: str) -> int | None:
    m = re.search(r"-?\d+", v or "")
    return int(m.group()) if m else None


def _to_number(v: str) -> float | int | None:
    m = re.search(r"-?\d+(?:\.\d+)?", (v or "").replace(",", ""))
    if not m:
        return None
    x = float(m.group())
    return int(x) if x.is_integer() else x


def _to_datetime(v: str) -> str | None:
    v = (v or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y.%m.%d %H:%M", "%Y%m%d%H%M",
                "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(v, fmt).isoformat(timespec="minutes")
        except ValueError:
            continue
    return None


def _option(value: str, options: list[Any], vmap: dict[str, str]) -> str | None:
    """Cell -> option value: the user's value map first, then an exact option value or label."""
    if value in vmap:
        return vmap[value]
    for o in options:
        if value == o.value or value == o.label:
            return o.value
    return None


def build_specs(template_key: str, rows: list[dict[str, str]], mapping: dict[str, Any], limit: int | None = None) -> dict[str, Any]:
    t = get_template(template_key)
    fields = {f.key: f for _, f in t.iter_fields()}
    cols: dict[str, str] = mapping.get("columns") or {}
    vmaps: dict[str, dict[str, str]] = mapping.get("values") or {}
    fixed: dict[str, Any] = mapping.get("fixed") or {}
    specs, warnings = [], []
    for i, row in enumerate(rows[: limit or len(rows)]):
        patient: dict[str, Any] = {"name": "", "age": None, "sex": "남", "diagnosis": "", "surgery": "", "professor": "", "department": "",
                                   "pod": None, "op_date": "", "admission_date": "", "kind": "op", "regimen": "", "cycle": None, "day": None}
        form = default_form(template_key)
        when: str | None = None
        for target, col in list(cols.items()) + [(k, None) for k in fixed]:
            raw = str(fixed[target]) if col is None else (row.get(col, "") or "")
            if col is not None and raw == "":
                continue
            raw = vmaps.get(target, {}).get(raw, raw) if col is not None else raw
            if target.startswith("patient."):
                k = target[8:]
                if k in _INT_FIELDS:
                    patient[k] = _to_int(raw)
                elif k == "sex":
                    patient[k] = "여" if raw.lower() in ("여", "f", "female", "여자", "여성", "w") else "남"
                elif k == "kind":
                    patient[k] = "chemo" if raw.lower() in ("chemo", "항암") else "op"
                else:
                    patient[k] = raw
            elif target == "datetime":
                when = _to_datetime(raw)
                if when is None:
                    warnings.append(f"{i + 1}행: 기록 일시 '{raw}'를 읽지 못해 현재 시각을 씁니다")
            elif target == "style":
                form["_style"] = raw
            elif target.startswith("form."):
                k = target[5:]
                f = fields.get(k)
                if f is None:
                    continue
                if f.kind == "select":
                    v = _option(raw, f.options, vmaps.get(target, {}))
                    if v is None:
                        warnings.append(f"{i + 1}행: '{f.label}' 값 '{raw}'에 맞는 선택지가 없어 기본값을 씁니다")
                    else:
                        form[k] = v
                elif f.kind == "multi":
                    picked = []
                    for part in re.split(r"[,;|/·]+", raw):
                        part = part.strip()
                        if not part:
                            continue
                        v = _option(part, f.options, vmaps.get(target, {}))
                        if v is None:
                            warnings.append(f"{i + 1}행: '{f.label}' 값 '{part}'에 맞는 선택지가 없습니다")
                        else:
                            picked.append(v)
                    if picked:
                        form[k] = picked
                elif f.kind == "number":
                    n = _to_number(raw)
                    if n is not None:
                        form[k] = n
                elif f.kind == "bool":
                    low = raw.strip().lower()
                    if low in _TRUE:
                        form[k] = True
                    elif low in _FALSE:
                        form[k] = False
                    else:
                        warnings.append(f"{i + 1}행: '{f.label}' 값 '{raw}'를 예/아니오로 읽지 못했습니다")
                else:
                    form[k] = raw
        if patient["regimen"] and not patient["surgery"]:
            patient["kind"] = "chemo"
        style = form.pop("_style", None)
        if not patient["name"]:
            warnings.append(f"{i + 1}행: 환자 성명이 비어 있어 '환자{i + 1}'로 씁니다")
            patient["name"] = f"환자{i + 1}"
        spec = {"template": template_key, "patient": patient, "form": form, "datetime": when or datetime.now().replace(second=0, microsecond=0).isoformat(timespec="minutes")}
        if style:
            spec["style"] = style
        specs.append(spec)
    return {"specs": specs, "warnings": warnings[:200], "warning_count": len(warnings)}


def _mappings_path():
    return data_dir() / "import_mappings.json"


def load_mappings() -> dict[str, Any]:
    p = _mappings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_mapping(template_key: str, mapping: dict[str, Any]) -> dict[str, Any]:
    allm = load_mappings()
    allm[template_key] = {"columns": mapping.get("columns") or {}, "values": mapping.get("values") or {}, "fixed": mapping.get("fixed") or {}}
    _mappings_path().parent.mkdir(parents=True, exist_ok=True)
    _mappings_path().write_text(json.dumps(allm, ensure_ascii=False, indent=2), encoding="utf-8")
    return allm[template_key]
