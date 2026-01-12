# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import yaml
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PlaywrightTimeoutError


ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    config_path = ROOT / "config.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def ensure_progress_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def sha256_text(value: str) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        value = str(value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def strip_parenthesized_text(value: str) -> str:
    return re.sub(r"\([^)]*\)", " ", value or "").strip()


def read_juso_confm_key_from_markdown(value: str) -> str | None:
    match = re.search(r"<승인키>\s*(.*?)\s*</승인키>", value or "", re.S)
    if not match:
        return None
    token = str(match.group(1) or "").strip()
    return token or None


def resolve_juso_confm_key(config: dict) -> str:
    juso_cfg = ((config.get("epost") or {}).get("script") or {}).get("juso_api") or {}

    env_name = str(juso_cfg.get("confm_key_env") or "").strip()
    if env_name:
        env_value = str(os.getenv(env_name) or "").strip()
        if env_value:
            return env_value

    fallback_path_value = str(juso_cfg.get("confm_key_fallback_path") or "").strip()
    if fallback_path_value:
        fallback_path = resolve_repo_path(fallback_path_value)
        if fallback_path.exists():
            token = read_juso_confm_key_from_markdown(
                fallback_path.read_text(encoding="utf-8")
            )
            if token:
                return token

    raise RuntimeError(
        "Juso API 승인키(confmKey)를 찾지 못했습니다. "
        f"환경변수({env_name or 'JUSO_CONFM_KEY'}) 또는 {fallback_path_value or 'juso.api/README_juso.md'}의 <승인키>를 확인하세요."
    )


def sanitize_juso_keyword(value: str) -> str:
    keyword = normalize_spaces(str(value or ""))
    keyword = strip_parenthesized_text(keyword)
    keyword = re.sub(r"[%=<>]", " ", keyword)
    return normalize_spaces(keyword)


def load_json_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_json_dict(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_juso_result_token(juso_item: dict) -> str:
    rn = normalize_spaces(str(juso_item.get("rn") or "")).strip()
    buld_mnnm = normalize_spaces(str(juso_item.get("buldMnnm") or "")).strip()
    buld_slno = normalize_spaces(str(juso_item.get("buldSlno") or "")).strip()
    if rn and buld_mnnm:
        suffix = f"-{buld_slno}" if buld_slno and buld_slno != "0" else ""
        return compact_spaces(f"{rn} {buld_mnnm}{suffix}")
    road_addr = normalize_spaces(
        str(juso_item.get("roadAddrPart1") or juso_item.get("roadAddr") or "")
    ).strip()
    return compact_spaces(road_addr)


def juso_address_search(config: dict, keyword: str) -> dict[str, str] | None:
    script_cfg = (config.get("epost") or {}).get("script") or {}
    juso_cfg = script_cfg.get("juso_api") or {}
    if not isinstance(juso_cfg, dict) or not juso_cfg.get("enabled", False):
        return None

    base_url = str(juso_cfg.get("base_url") or "").strip()
    if not base_url:
        raise ValueError("config.yaml의 epost.script.juso_api.base_url 설정이 비어 있습니다.")

    sanitized_keyword = sanitize_juso_keyword(keyword)
    if not sanitized_keyword:
        return None

    cache_path_value = str(juso_cfg.get("cache_path") or "").strip()
    cache_path = resolve_repo_path(cache_path_value) if cache_path_value else None
    cache_key = compact_spaces(sanitized_keyword)
    cache: dict = {}
    if cache_path:
        cache = load_json_dict(cache_path)
        if cache_key in cache and isinstance(cache.get(cache_key), dict):
            cached = cache[cache_key]
            return {k: str(v) for k, v in cached.items() if v is not None}

    confm_key = resolve_juso_confm_key(config)

    count_per_page = juso_cfg.get("count_per_page", 10)
    try:
        count_per_page_int = int(count_per_page)
    except (TypeError, ValueError):
        count_per_page_int = 10
    count_per_page_int = max(1, min(100, count_per_page_int))

    timeout_ms = juso_cfg.get("timeout_ms", 15000)
    try:
        timeout_ms_int = int(timeout_ms)
    except (TypeError, ValueError):
        timeout_ms_int = 15000
    timeout_s = max(1.0, timeout_ms_int / 1000.0)

    params = {
        "confmKey": confm_key,
        "keyword": sanitized_keyword,
        "currentPage": 1,
        "countPerPage": count_per_page_int,
        "resultType": str(juso_cfg.get("result_type") or "json").strip() or "json",
    }
    request_url = f"{base_url}?{urlencode(params)}"
    req = Request(request_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout_s) as response:
        payload_text = response.read().decode("utf-8")
    data = json.loads(payload_text)

    results = data.get("results") if isinstance(data, dict) else None
    common = (results or {}).get("common") if isinstance(results, dict) else None
    error_code = str((common or {}).get("errorCode") or "").strip()
    if error_code != "0":
        error_message = str((common or {}).get("errorMessage") or "").strip()
        raise RuntimeError(f"Juso 주소검색 실패(errorCode={error_code}): {error_message}")

    juso_list = (results or {}).get("juso") if isinstance(results, dict) else None
    if not isinstance(juso_list, list) or not juso_list:
        return None

    selected = juso_list[0]
    if not isinstance(selected, dict):
        return None

    record: dict[str, str] = {}
    for field in (
        "roadAddr",
        "roadAddrPart1",
        "roadAddrPart2",
        "jibunAddr",
        "zipNo",
        "rn",
        "buldMnnm",
        "buldSlno",
        "bdNm",
        "siNm",
        "sggNm",
        "emdNm",
    ):
        value = selected.get(field)
        if value is None:
            continue
        record[field] = str(value)
    record["result_text_contains"] = build_juso_result_token(selected)

    if cache_path:
        cache[cache_key] = record
        save_json_dict(cache_path, cache)
    return record


def parse_sender_phone_parts(value: object) -> tuple[str, str]:
    digits = re.sub(r"\D+", "", str(value or ""))
    if digits.startswith("82"):
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits.startswith("10"):
        digits = "0" + digits
    if len(digits) > 11:
        if "010" in digits:
            start = digits.find("010")
            digits = digits[start : start + 11]
        else:
            digits = digits[-11:]
    if len(digits) != 11:
        raise ValueError(f"휴대전화 형식이 올바르지 않습니다: {value!r}")
    return digits[3:7], digits[7:11]


def parse_ymd_date(value: object) -> str:
    if value is None:
        raise ValueError("방문일 값이 비어 있습니다.")
    if isinstance(value, datetime):
        return value.date().strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()
    match = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    raise ValueError(f"방문일 형식이 올바르지 않습니다: {value!r}")


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact_spaces(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def safe_filename_token(value: str, max_len: int = 40) -> str:
    token = normalize_spaces(str(value or "")).strip()
    token = re.sub(r'[<>:"/\\\\|?*]+', "_", token)
    token = token.replace(" ", "_").strip("._")
    if not token:
        token = "unknown"
    if len(token) > max_len:
        token = token[:max_len].rstrip("._")
    return token


def parse_pickup_address_rule_legacy(value: object) -> dict[str, str | None]:
    raw = normalize_spaces(str(value or ""))
    if not raw:
        raise ValueError("택배 회수장소 주소 값이 비어 있습니다.")

    unit_match = None
    for match in re.finditer(r"(\d{1,4})\s*호", raw):
        unit_match = match
    unit = unit_match.group(1) if unit_match else None

    building: str | None = None
    if unit_match:
        unit_pos = unit_match.start()
        building_candidates = [
            m
            for m in re.finditer(r"((?:\d{1,4}|[A-Za-z]|[가-힣]))\s*동", raw)
            if m.start() < unit_pos
        ]
        if building_candidates:
            closest = min(building_candidates, key=lambda m: unit_pos - m.start())
            building = closest.group(1)
    else:
        building_match = re.search(r"(\d{1,4})\s*동", raw)
        building = building_match.group(1) if building_match else None

    keyword = raw.split(",", 1)[0].strip()
    if not keyword:
        keyword = raw

    if building:
        details_match = re.search(re.escape(building) + r"\s*동", keyword)
        if details_match:
            keyword = keyword[: details_match.start()].strip().rstrip(",")
    if unit:
        details_match = re.search(re.escape(unit) + r"\s*호", keyword)
        if details_match:
            keyword = keyword[: details_match.start()].strip().rstrip(",")

    road_pattern = r"[가-힣0-9]+(?:로|길|대로)\s*\d+(?:-\d+)?(?:\s*번길\s*\d+(?:-\d+)?)?(?=$|[,\s(])"
    road_match = re.search(road_pattern, keyword) or re.search(road_pattern, raw)
    if road_match:
        result_token = compact_spaces(road_match.group(0))
    else:
        result_token = compact_spaces(keyword or raw)

    return {
        "raw": raw,
        "keyword": keyword,
        "result_text_contains": result_token,
        "building": building,
        "unit": unit,
    }


def parse_pickup_address_rule(value: object) -> dict[str, str | None]:
    raw_source = normalize_spaces(str(value or ""))
    if not raw_source:
        raise ValueError("택배 회수장소 주소 값이 비어 있습니다.")

    raw = normalize_spaces(strip_parenthesized_text(raw_source))
    if not raw:
        raise ValueError("택배 회수장소 주소 값이 비어 있습니다.")

    road_pattern = (
        r"[가-힣0-9]+(?:로|길|대로)\s*\d+(?:-\d+)?(?:\s*번길\s*\d+(?:-\d+)?)?(?=$|[,\s(])"
    )
    road_match = re.search(road_pattern, raw)

    keyword = ""
    detail_address: str | None = None
    if road_match:
        keyword = raw[: road_match.end()].strip().rstrip(",")
        remainder = raw[road_match.end() :].strip()
        remainder = remainder.lstrip(",").strip()
        detail_address = remainder or None
    else:
        keyword = raw.split(",", 1)[0].strip() or raw
        if "," in raw:
            remainder = raw.split(",", 1)[1].strip()
            detail_address = remainder or None

    unit_match = None
    unit_source = detail_address or raw
    for match in re.finditer(r"(\d{1,4})\s*호", unit_source):
        unit_match = match
    unit = unit_match.group(1) if unit_match else None

    building: str | None = None
    building_pattern = r"((?:\d{1,4}|[A-Za-z]|[가-힣]))\s*동"
    if unit_match:
        unit_pos = unit_match.start()
        building_candidates = [
            m for m in re.finditer(building_pattern, unit_source) if m.start() < unit_pos
        ]
        if building_candidates:
            closest = min(building_candidates, key=lambda m: unit_pos - m.start())
            building = closest.group(1)
    else:
        building_match = re.search(building_pattern, unit_source)
        building = building_match.group(1) if building_match else None

    road_match_for_token = road_match or re.search(road_pattern, keyword) or re.search(
        road_pattern, raw
    )
    if road_match_for_token:
        result_token = compact_spaces(road_match_for_token.group(0))
    else:
        result_token = compact_spaces(keyword or raw)

    return {
        "raw": raw,
        "keyword": keyword,
        "result_text_contains": result_token,
        "detail_address": detail_address,
        "building": building,
        "unit": unit,
    }


def looks_like_road_token(value: str) -> bool:
    token = compact_spaces(str(value or ""))
    if not token:
        return False
    road_token_pattern = (
        r"[가-힣0-9]+(?:로|길|대로)\d+(?:-\d+)?(?:번길\d+(?:-\d+)?)?"
    )
    return re.fullmatch(road_token_pattern, token) is not None


def parse_pickup_address(value: object, config: dict) -> dict[str, object]:
    rule = parse_pickup_address_rule(value)
    token = str(rule.get("result_text_contains") or "").strip()

    script_cfg = (config.get("epost") or {}).get("script") or {}
    juso_cfg = script_cfg.get("juso_api") if isinstance(script_cfg, dict) else {}
    juso_cfg = juso_cfg if isinstance(juso_cfg, dict) else {}
    mode = str(juso_cfg.get("mode") or "if_needed").strip().lower()
    if mode not in {"always", "if_needed"}:
        mode = "if_needed"

    token_road_like = looks_like_road_token(token)
    api_checked = False
    api_hit = False
    api_adjusted = False
    api_error: str | None = None

    if mode == "if_needed" and token_road_like:
        rule["api_checked"] = api_checked
        rule["api_hit"] = api_hit
        rule["api_adjusted"] = api_adjusted
        rule["api_error"] = api_error
        return rule

    keyword = str(rule.get("keyword") or rule.get("raw") or "").strip()
    if not keyword:
        rule["api_checked"] = api_checked
        rule["api_hit"] = api_hit
        rule["api_adjusted"] = api_adjusted
        rule["api_error"] = api_error
        return rule

    before_keyword = str(rule.get("keyword") or "").strip()
    before_token = str(rule.get("result_text_contains") or "").strip()

    try:
        api_checked = True
        juso_record = juso_address_search(config, keyword)
    except Exception as exc:
        api_error = f"{type(exc).__name__}: {exc}"
        juso_record = None

    if not juso_record:
        rule["api_checked"] = api_checked
        rule["api_hit"] = api_hit
        rule["api_adjusted"] = api_adjusted
        rule["api_error"] = api_error
        return rule

    api_hit = True

    road_keyword = str(
        juso_record.get("roadAddrPart1") or juso_record.get("roadAddr") or ""
    ).strip()
    if road_keyword:
        rule["keyword"] = road_keyword

    result_text_contains = str(juso_record.get("result_text_contains") or "").strip()
    if result_text_contains:
        rule["result_text_contains"] = result_text_contains

    after_keyword = str(rule.get("keyword") or "").strip()
    after_token = str(rule.get("result_text_contains") or "").strip()
    api_adjusted = (after_keyword != before_keyword) or (after_token != before_token)

    rule["api_checked"] = api_checked
    rule["api_hit"] = api_hit
    rule["api_adjusted"] = api_adjusted
    rule["api_error"] = api_error
    return rule


def get_excel_targets(config: dict) -> list[dict[str, str]]:
    excel_cfg = config.get("input_excel") or {}
    if not excel_cfg:
        return []

    targets_raw = excel_cfg.get("targets")
    if isinstance(targets_raw, list) and targets_raw:
        targets: list[dict[str, str]] = []
        for idx, target in enumerate(targets_raw):
            if not isinstance(target, dict):
                raise ValueError(f"config.yaml의 input_excel.targets[{idx}]가 dict가 아닙니다.")
            management_no = str(target.get("management_no") or "").strip()
            subject_name = str(target.get("subject_name") or "").strip()
            if not management_no or not subject_name:
                raise ValueError(
                    f"config.yaml의 input_excel.targets[{idx}]에 management_no/subject_name이 필요합니다."
                )
            targets.append({"management_no": management_no, "subject_name": subject_name})
        return targets

    filter_cfg = excel_cfg.get("filter") or {}
    mgmt_cfg = filter_cfg.get("management_no") or {}
    name_cfg = filter_cfg.get("subject_name") or {}
    management_no = str(mgmt_cfg.get("value") or "").strip()
    subject_name = str(name_cfg.get("value") or "").strip()
    if not management_no or not subject_name:
        raise ValueError("config.yaml의 input_excel.targets 또는 input_excel.filter.*.value 설정이 필요합니다.")
    return [{"management_no": management_no, "subject_name": subject_name}]


def load_subject_dataframe_from_excel(config: dict):
    excel_cfg = config.get("input_excel") or {}
    if not excel_cfg:
        raise ValueError("config.yaml의 input_excel 설정이 없습니다.")

    excel_path = resolve_repo_path(excel_cfg.get("path") or "")
    sheet_name = excel_cfg.get("sheet_name")
    if not excel_path.exists():
        raise FileNotFoundError(f"엑셀 파일을 찾지 못했습니다: {excel_path}")
    if not sheet_name:
        raise ValueError("config.yaml의 input_excel.sheet_name 설정이 비어 있습니다.")

    filter_cfg = excel_cfg.get("filter") or {}
    mgmt_cfg = filter_cfg.get("management_no") or {}
    name_cfg = filter_cfg.get("subject_name") or {}
    mgmt_col = str(mgmt_cfg.get("column") or "").strip()
    name_col = str(name_cfg.get("column") or "").strip()
    if not mgmt_col:
        raise ValueError("config.yaml의 input_excel.filter.management_no.column 설정이 올바르지 않습니다.")
    if not name_col:
        raise ValueError("config.yaml의 input_excel.filter.subject_name.column 설정이 올바르지 않습니다.")

    columns_to_read = {mgmt_col, name_col}
    for col_name in (excel_cfg.get("columns") or {}).values():
        col_str = str(col_name or "").strip()
        if col_str:
            columns_to_read.add(col_str)

    import polars as pl

    df = pl.read_excel(
        str(excel_path),
        sheet_name=str(sheet_name),
        columns=sorted(columns_to_read),
    )
    return df, excel_path, str(sheet_name), mgmt_col, name_col


def load_subject_row_from_dataframe(
    df,
    management_no_col: str,
    subject_name_col: str,
    management_no: str,
    subject_name: str,
    excel_path: Path,
    sheet_name: str,
) -> dict[str, object]:
    mgmt_value = str(management_no or "").strip()
    name_value = str(subject_name or "").strip()
    if not mgmt_value or not name_value:
        raise ValueError("대상자 관리번호/이름이 비어 있습니다.")

    import polars as pl

    filtered = df.filter(
        (pl.col(str(management_no_col)).cast(pl.Utf8).str.strip_chars() == mgmt_value)
        & (pl.col(str(subject_name_col)).cast(pl.Utf8).str.strip_chars() == name_value)
    )
    if filtered.height == 0:
        raise ValueError(
            f"엑셀에서 대상자 행을 찾지 못했습니다: "
            f"{management_no_col}={mgmt_value!r}, {subject_name_col}={name_value!r} "
            f"(파일={excel_path}, 시트={sheet_name})"
        )
    return filtered.row(0, named=True)


def apply_excel_overrides(config: dict, row: dict[str, object], target: dict[str, str] | None = None) -> None:
    # input_excel이 최상위 레벨로 이동됨
    excel_cfg = config.get("input_excel") or {}
    if not excel_cfg:
        return

    columns_cfg = excel_cfg.get("columns") or {}
    sender_name_col = columns_cfg.get("sender_name")
    contact_col = columns_cfg.get("sender_contact")
    wish_date_col = columns_cfg.get("wish_receipt_date")
    pickup_address_col = columns_cfg.get("pickup_address")
    if not contact_col or not wish_date_col or not pickup_address_col:
        raise ValueError("config.yaml의 input_excel.columns 설정이 올바르지 않습니다.")

    sender_name_value: object | None = None
    if sender_name_col:
        sender_name_value = row.get(str(sender_name_col))
    else:
        filter_cfg = excel_cfg.get("filter") or {}
        fallback_name_cfg = filter_cfg.get("subject_name") or {}
        fallback_col = fallback_name_cfg.get("column")
        if fallback_col:
            sender_name_value = row.get(str(fallback_col))
        else:
            sender_name_value = (target or {}).get("subject_name") or fallback_name_cfg.get("value")
    sender_name = normalize_spaces(str(sender_name_value or "")).strip()
    if not sender_name:
        raise ValueError("엑셀에서 보내는 분 이름 값이 비어 있습니다.")

    sender_middle, sender_last = parse_sender_phone_parts(row.get(str(contact_col)))
    wish_receipt_date = parse_ymd_date(row.get(str(wish_date_col)))
    pickup_address = str(row.get(str(pickup_address_col)) or "").strip()
    if not pickup_address:
        raise ValueError("엑셀의 택배 회수장소 주소 값이 비어 있습니다.")

    # working_process에서 workflow로 변경됨
    epost_cfg = config.get("epost") or {}
    workflow_cfg = epost_cfg.get("workflow") or {}

    # Step 01 sender 오버라이드
    sender_cfg = workflow_cfg.get("step_01_sender") or {}
    sender_cfg["name"] = sender_name
    sender_phone_cfg = sender_cfg.get("phone") or {}
    sender_phone_cfg["middle"] = sender_middle
    sender_phone_cfg["last"] = sender_last
    sender_cfg["phone"] = sender_phone_cfg
    workflow_cfg["step_01_sender"] = sender_cfg

    # Step 02 pickup_info 오버라이드
    pickup_cfg = workflow_cfg.get("step_02_pickup_info") or {}
    pickup_cfg["wish_receipt_date"] = wish_receipt_date
    workflow_cfg["step_02_pickup_info"] = pickup_cfg

    # Shared address_popup 오버라이드
    try:
        pickup_rule = parse_pickup_address(pickup_address, config)
    except ValueError:
        pickup_rule = {}

    keyword = str(pickup_rule.get("keyword") or "").strip()
    if keyword:
        shared_cfg = workflow_cfg.get("shared") or {}
        popup_cfg = shared_cfg.get("address_popup") or {}
        popup_cfg["keyword"] = keyword
        popup_cfg["result_text_contains"] = str(pickup_rule.get("result_text_contains") or "").strip() or compact_spaces(
            keyword
        )

        detail_address = normalize_spaces(
            str(pickup_rule.get("detail_address") or "")
        ).strip()
        if detail_address:
            popup_cfg["detail_address"] = detail_address
        else:
            popup_cfg.pop("detail_address", None)

        building = pickup_rule.get("building")
        unit = pickup_rule.get("unit")
        if building and unit:
            popup_cfg["building"] = str(building)
            popup_cfg["unit"] = str(unit)
        else:
            popup_cfg.pop("building", None)
            popup_cfg.pop("unit", None)
        shared_cfg["address_popup"] = popup_cfg
        workflow_cfg["shared"] = shared_cfg

    epost_cfg["workflow"] = workflow_cfg
    config["epost"] = epost_cfg


def validate_excel_overrides_applied(
    config: dict, target: dict[str, str] | None = None
) -> None:
    epost_cfg = config.get("epost") or {}
    workflow_cfg = epost_cfg.get("workflow") or {}

    sender_cfg = workflow_cfg.get("step_01_sender") or {}
    sender_phone_cfg = sender_cfg.get("phone") or {}
    pickup_cfg = workflow_cfg.get("step_02_pickup_info") or {}

    sender_name = normalize_spaces(str(sender_cfg.get("name") or "")).strip()
    sender_middle = str(sender_phone_cfg.get("middle") or "").strip()
    sender_last = str(sender_phone_cfg.get("last") or "").strip()
    wish_receipt_date = str(pickup_cfg.get("wish_receipt_date") or "").strip()

    missing: list[str] = []
    if not sender_name:
        missing.append("epost.workflow.step_01_sender.name")
    if not sender_middle:
        missing.append("epost.workflow.step_01_sender.phone.middle")
    if not sender_last:
        missing.append("epost.workflow.step_01_sender.phone.last")
    if not wish_receipt_date:
        missing.append("epost.workflow.step_02_pickup_info.wish_receipt_date")

    if missing:
        prefix = ""
        if target:
            mgmt = str(target.get("management_no") or "").strip()
            name = str(target.get("subject_name") or "").strip()
            if mgmt or name:
                prefix = f"대상자(관리번호={mgmt or '?'}, 이름={name or '?'}) "
        raise ValueError(
            prefix + "엑셀 오버라이드 후 필수 값이 비어 있습니다: " + ", ".join(missing)
        )

    if sender_middle and not re.fullmatch(r"\d{4}", sender_middle):
        raise ValueError(f"보내는 분 휴대전화 중간자리 형식이 올바르지 않습니다: {sender_middle!r}")
    if sender_last and not re.fullmatch(r"\d{4}", sender_last):
        raise ValueError(f"보내는 분 휴대전화 뒷자리 형식이 올바르지 않습니다: {sender_last!r}")
    if wish_receipt_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", wish_receipt_date):
        raise ValueError(f"방문일 형식이 올바르지 않습니다: {wish_receipt_date!r}")


def collect_validation_snapshot(page) -> dict:
    fields_spec = {
        "wish_receipt_date": {"selector": ['select[name="wishReceiptTime"]'], "kind": "value"},
        "wish_receipt_time": {"selector": ['select[name="wishReceiptTimeNm"]'], "kind": "value"},
        "pickup_keep": {"selector": ['select[name="pickupKeep"]'], "kind": "value"},
        "pickup_keep_note": {"selector": ['input[name="pickupKeepNm"]'], "kind": "value"},
        "weight_code": {"selector": ["#limit_wg", "#tmpWght1"], "kind": "value"},
        "volume_code": {"selector": ["#limit_vol", "#tmpVol1"], "kind": "value"},
        "product_code": {"selector": ["#labProductCode"], "kind": "value"},
        "contents": {"selector": ["#labcont"], "kind": "value"},
        "delivery_note": {"selector": ["#labdemand"], "kind": "value"},
        "receiver_name": {"selector": ['input[name="receiverName"]'], "kind": "value"},
        "receiver_detail_address": {"selector": ['input[name="reDetailAddr"]'], "kind": "value"},
        "receiver_phone_1": {"selector": ["#reCell1"], "kind": "value"},
        "receiver_phone_2": {"selector": ["#reCell2"], "kind": "value"},
        "receiver_phone_3": {"selector": ["#reCell3"], "kind": "value"},
        "payment_card_no1": {"selector": ["#creditNo1"], "kind": "value"},
        "payment_card_no2": {"selector": ["#creditNo2"], "kind": "value"},
        "payment_card_no3": {"selector": ["#creditNo3"], "kind": "value"},
        "payment_card_no4": {"selector": ["#creditNo4"], "kind": "value"},
        "payment_expiry_month": {"selector": ["#creditExp1"], "kind": "value"},
        "payment_expiry_year": {"selector": ["#creditExp2"], "kind": "value"},
        "payment_password_digit1": {"selector": ["#creditPwd1"], "kind": "value"},
        "payment_password_digit2": {"selector": ["#creditPwd2"], "kind": "value"},
        "payment_birthdate": {"selector": ["#creditBirth"], "kind": "value"},
        "payment_mobile_receipt_yes": {"selector": ["#mreceipt_y"], "kind": "checked"},
        "payment_mobile_receipt_no": {"selector": ["#mreceipt_n"], "kind": "checked"},
    }

    raw_fields = page.evaluate(
        """(spec) => {
            const out = {};
            const pickFirst = (selectors) => {
                const list = Array.isArray(selectors) ? selectors : [selectors];
                for (const sel of list) {
                    if (!sel) continue;
                    const el = document.querySelector(sel);
                    if (el) return el;
                }
                return null;
            };

            for (const [key, cfg] of Object.entries(spec || {})) {
                const el = pickFirst(cfg.selector);
                if (!el) {
                    out[key] = null;
                    continue;
                }
                if (cfg.kind === 'checked') {
                    out[key] = !!el.checked;
                } else if (cfg.kind === 'text') {
                    out[key] = (el.textContent || '').toString();
                } else {
                    out[key] = (el.value ?? '').toString();
                }
            }
            return out;
        }""",
        fields_spec,
    )

    title = ""
    try:
        title = page.title() or ""
    except PlaywrightError:
        title = ""

    url = ""
    try:
        url = canonicalize_url(page.url)
    except Exception:
        url = ""

    fields: dict[str, object] = {}
    for key, value in (raw_fields or {}).items():
        if value is None:
            fields[key] = None
            continue
        if isinstance(value, str):
            cleaned = value.strip()
        else:
            cleaned = value

        if key.startswith("payment_") and key not in {"payment_mobile_receipt_yes", "payment_mobile_receipt_no"}:
            fields[key] = sha256_text(str(cleaned))
        else:
            fields[key] = cleaned

    return {"url": url, "title": title, "fields": fields}


def write_success_artifacts(page, progress_dir: Path, prefix: str) -> tuple[Path, Path] | None:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = progress_dir / f"{prefix}_{timestamp}.png"
    snapshot_path = progress_dir / f"{prefix}_{timestamp}.jsonl"
    try:
        snapshot = collect_validation_snapshot(page)
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return None

    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        pass

    return screenshot_path, snapshot_path


def step_delay(page, timeout_ms: int | None) -> None:
    if timeout_ms and timeout_ms > 0:
        if hasattr(page, "is_closed") and page.is_closed():
            return
        try:
            page.wait_for_timeout(timeout_ms)
        except PlaywrightError:
            pass


def wait_for_manual_close(page, keep_open: bool, poll_ms: int) -> None:
    if not keep_open:
        return
    wait_ms = poll_ms if poll_ms and poll_ms > 0 else 1000
    try:
        while True:
            if hasattr(page, "is_closed") and page.is_closed():
                break
            try:
                page.wait_for_timeout(wait_ms)
            except PlaywrightError:
                break
    except KeyboardInterrupt:
        pass


def dismiss_dialog_safely(dialog) -> None:
    try:
        dialog.dismiss()
    except PlaywrightError:
        pass


def accept_dialog_safely(dialog) -> None:
    try:
        dialog.accept()
    except PlaywrightError:
        try:
            dialog.dismiss()
        except PlaywrightError:
            pass


def set_input_value(page, selector: str, value: str, timeout_ms: int | None = None) -> bool:
    if value is None:
        return False
    updated = page.evaluate(
        """(payload) => {
            const el = document.querySelector(payload.selector);
            if (!el) return false;
            el.value = payload.value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""",
        {"selector": selector, "value": value},
    )
    if updated:
        step_delay(page, timeout_ms)
    return updated


def set_select_value(page, selector: str, value: str, timeout_ms: int | None = None) -> bool:
    if value is None:
        return False
    result = page.evaluate(
        """(payload) => {
            const el = document.querySelector(payload.selector);
            if (!el) return { ok: false, reason: 'not_found' };

            const desiredRaw = (payload.value ?? '').toString();
            const desired = desiredRaw.trim();
            const normalize = (text) => (text || '').toString().replace(/\\s+/g, '').trim();
            const digits = (text) => (text || '').toString().replace(/\\D+/g, '');

            const dispatch = () => {
                try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (e) {}
                try { el.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
            };

            const setValue = (v) => {
                el.value = v;
                dispatch();
                return el.value === v;
            };

            if (setValue(desired)) {
                return { ok: true, matched: 'value', used: desired, current: el.value };
            }

            const options = Array.from(el.options || []);
            const desiredCompact = normalize(desired);
            const desiredDigits = digits(desiredCompact);

            const matchByTextOrValue = () => {
                if (!desired) return null;
                let match =
                    options.find((opt) => (opt.value || '') === desired) ||
                    options.find((opt) => normalize(opt.textContent || '') === desiredCompact) ||
                    options.find((opt) => normalize(opt.textContent || '').includes(desiredCompact)) ||
                    options.find((opt) => normalize(opt.value || '').includes(desiredCompact));
                if (match) return match;
                if (desiredDigits) {
                    match =
                        options.find((opt) => digits(opt.value || '') === desiredDigits) ||
                        options.find((opt) => digits(opt.textContent || '') === desiredDigits) ||
                        options.find((opt) => digits(opt.textContent || '').includes(desiredDigits)) ||
                        options.find((opt) => digits(opt.value || '').includes(desiredDigits));
                }
                return match || null;
            };

            const match = matchByTextOrValue();
            if (match && setValue(match.value)) {
                return { ok: true, matched: 'option_match', used: match.value, current: el.value };
            }

            const isDateDigits = desiredDigits.length >= 8 && desiredDigits.startsWith('20');
            if (isDateDigits && options.length) {
                const desiredDateDigits = desiredDigits.slice(0, 8);
                const desiredInt = parseInt(desiredDateDigits, 10);
                const candidates = options
                    .map((opt) => {
                        const textDigits = digits(opt.textContent || '');
                        const valueDigits = digits(opt.value || '');
                        const merged = (textDigits || valueDigits || '').toString();
                        const dateDigits = merged.startsWith('20') && merged.length >= 8 ? merged.slice(0, 8) : '';
                        const dateInt = dateDigits ? parseInt(dateDigits, 10) : NaN;
                        return { opt, dateInt };
                    })
                    .filter((row) => Number.isFinite(row.dateInt));

                if (candidates.length) {
                    const future = candidates
                        .filter((row) => row.dateInt >= desiredInt)
                        .sort((a, b) => a.dateInt - b.dateInt)[0];
                    const fallback = candidates.sort((a, b) => a.dateInt - b.dateInt)[0];
                    const chosen = (future || fallback).opt;
                    if (chosen && setValue(chosen.value)) {
                        return { ok: true, matched: 'closest_date', used: chosen.value, current: el.value };
                    }
                }
            }

            const fallbackOption = options.find((opt) => (opt.value || '').toString().trim() !== '');
            if (fallbackOption && setValue(fallbackOption.value)) {
                return { ok: true, matched: 'fallback_first', used: fallbackOption.value, current: el.value };
            }

            return { ok: false, reason: 'no_match', current: el.value };
        }""",
        {"selector": selector, "value": value},
    )
    updated = bool(result and result.get("ok"))
    if updated:
        step_delay(page, timeout_ms)
    return updated


def set_checkbox_checked(page, selector: str, checked: bool, timeout_ms: int | None = None) -> bool:
    updated = page.evaluate(
        """(payload) => {
            const el = document.querySelector(payload.selector);
            if (!el) return false;
            if (typeof el.checked === 'undefined') return false;
            el.checked = payload.checked;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""",
        {"selector": selector, "checked": checked},
    )
    if updated:
        step_delay(page, timeout_ms)
    return updated


def set_select_value_any(page, selectors: list[str], value: str, timeout_ms: int | None = None) -> bool:
    if value is None:
        return False
    for selector in selectors:
        if not selector:
            continue
        if set_select_value(page, selector, value, timeout_ms):
            return True
    return False


def set_input_value_any(page, selectors: list[str], value: str, timeout_ms: int | None = None) -> bool:
    if value is None:
        return False
    for selector in selectors:
        if not selector:
            continue
        if set_input_value(page, selector, value, timeout_ms):
            return True
    return False


def set_input_by_label_tokens(page, label_tokens: list[str], value: str, timeout_ms: int | None = None) -> bool:
    if value is None or not label_tokens:
        return False
    updated = page.evaluate(
        """(payload) => {
            const tokens = payload.tokens || [];
            if (!tokens.length) return false;
            const labels = Array.from(document.querySelectorAll('label'));
            const label = labels.find(el => tokens.some(token => (el.textContent || '').includes(token)));
            if (!label) return false;

            const forId = label.getAttribute('for');
            let field = forId ? document.getElementById(forId) : null;
            if (!field) {
                field = label.querySelector('input, textarea');
            }
            if (!field) {
                const scope = label.closest('tr, li, div');
                if (scope) field = scope.querySelector('input, textarea');
            }
            if (!field) return false;

            field.value = payload.value;
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""",
        {"tokens": label_tokens, "value": value},
    )
    if updated:
        step_delay(page, timeout_ms)
    return updated


def set_input_by_associated_text_tokens(page, text_tokens: list[str], value: str, timeout_ms: int | None = None) -> bool:
    if value is None or not text_tokens:
        return False
    updated = page.evaluate(
        """(payload) => {
            const tokensRaw = Array.isArray(payload.tokens) ? payload.tokens : [payload.tokens];
            const tokens = tokensRaw.map((t) => (t ?? '').toString()).filter(Boolean);
            if (!tokens.length) return false;

            const value = (payload.value ?? '').toString();
            const normalize = (s) => (s || '').toString().replace(/\\s+/g, '').trim();
            const tokenNorm = tokens.map(normalize).filter(Boolean);
            if (!tokenNorm.length) return false;

            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };

            const escapeCss = (value) => {
                try {
                    if (typeof CSS !== 'undefined' && CSS && typeof CSS.escape === 'function') return CSS.escape(value);
                } catch (e) {}
                return value.replace(/\"/g, '\\\\\"');
            };

            const assocText = (el) => {
                const attrs = [
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('placeholder') || '',
                ].join(' ').trim();
                if (attrs) return attrs;

                const id = el.getAttribute('id') || '';
                if (id) {
                    const label = document.querySelector(`label[for=\"${escapeCss(id)}\"]`);
                    if (label) return (label.textContent || '').toString();
                }

                const parentLabel = el.closest('label');
                if (parentLabel) return (parentLabel.textContent || '').toString();

                const row = el.closest('tr');
                if (row) {
                    const header = row.querySelector('th') || row.querySelector('td');
                    if (header) return (header.textContent || '').toString();
                }

                const container = el.closest('td, div, li');
                if (container) {
                    let prev = container.previousElementSibling;
                    while (prev) {
                        const txt = (prev.textContent || '').toString().trim();
                        if (txt) return txt;
                        prev = prev.previousElementSibling;
                    }
                }

                return '';
            };

            const candidates = Array.from(document.querySelectorAll('input, textarea')).filter((el) => {
                const tag = (el.tagName || '').toLowerCase();
                if (tag === 'textarea') return true;
                if (tag !== 'input') return false;
                const type = ((el.getAttribute('type') || 'text') + '').toLowerCase();
                return type === 'text' || type === 'tel' || type === 'search' || type === '';
            });

            for (const el of candidates) {
                if (!isVisible(el)) continue;
                const text = assocText(el);
                const normalized = normalize(text);
                if (!normalized) continue;
                if (!tokenNorm.some((token) => normalized.includes(token))) continue;

                el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }

            return false;
        }""",
        {"tokens": text_tokens, "value": value},
    )
    if updated:
        step_delay(page, timeout_ms)
    return updated


def click_selector(page, selector: str, timeout_ms: int | None = None) -> bool:
    clicked = page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
            const rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return false;
            if (typeof el.disabled !== 'undefined' && el.disabled) return false;
            el.click();
            return true;
        }""",
        selector,
    )
    if clicked:
        step_delay(page, timeout_ms)
    return clicked


def click_link_by_text(
    page, text: str, container_selector: str | None = None, timeout_ms: int | None = None
) -> bool:
    clicked = page.evaluate(
        """(payload) => {
            const root = payload.container ? document.querySelector(payload.container) : document;
            if (!root) return false;
            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };
            const links = Array.from(root.querySelectorAll('a')).filter(isVisible);
            const target = links.find(link => (link.textContent || '').includes(payload.text));
            if (!target) return false;
            target.click();
            return true;
        }""",
        {"text": text, "container": container_selector},
    )
    if clicked:
        step_delay(page, timeout_ms)
    return clicked


def click_link_by_text_index(
    page,
    text: str,
    index: int = 0,
    container_selector: str | None = None,
    timeout_ms: int | None = None,
) -> bool:
    clicked = page.evaluate(
        """(payload) => {
            const root = payload.container ? document.querySelector(payload.container) : document;
            if (!root) return false;
            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };
            const candidates = Array.from(root.querySelectorAll('a, button, [role="button"], [role="link"]'));
            const matches = candidates.filter((el) => {
                const text = (el.textContent || '').trim();
                const aria = (el.getAttribute('aria-label') || '').trim();
                const title = (el.getAttribute('title') || '').trim();
                const imgAlt = (el.querySelector('img[alt]')?.getAttribute('alt') || '').trim();
                return (
                    text.includes(payload.text)
                    || aria.includes(payload.text)
                    || title.includes(payload.text)
                    || imgAlt.includes(payload.text)
                );
            });
            const visibleMatches = matches.filter(isVisible);
            const targetList = visibleMatches.length ? visibleMatches : matches;
            const target = targetList[payload.index];
            if (!target) return false;
            target.click();
            return true;
        }""",
        {"text": text, "index": index, "container": container_selector},
    )
    if clicked:
        step_delay(page, timeout_ms)
    return clicked


def click_visible_element_by_text(
    page,
    selectors: list[str],
    text_tokens: list[str],
    timeout_ms: int | None = None,
    prefer_last: bool = False,
) -> bool:
    if not selectors:
        return False
    clicked = page.evaluate(
        """(payload) => {
            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };
            const tokens = payload.text_tokens || [];
            const matchesText = (el) => {
                if (tokens.length === 0) return true;
                const text = (el.textContent || el.value || '').trim();
                const aria = (el.getAttribute('aria-label') || '').trim();
                const title = (el.getAttribute('title') || '').trim();
                const imgAlt = (el.querySelector('img[alt]')?.getAttribute('alt') || '').trim();
                return tokens.some(
                    token => text.includes(token) || aria.includes(token) || title.includes(token) || imgAlt.includes(token)
                );
            };
            const matches = [];
            for (const selector of payload.selectors || []) {
                const elements = Array.from(document.querySelectorAll(selector));
                for (const el of elements) {
                    if (el.disabled) continue;
                    if (!isVisible(el)) continue;
                    if (!matchesText(el)) continue;
                    matches.push(el);
                }
            }
            if (!matches.length) return false;

            const preferLast = !!payload.prefer_last;
            let target = matches[0];
            if (preferLast) {
                target = matches
                    .map((el) => ({ el, top: el.getBoundingClientRect().top }))
                    .sort((a, b) => a.top - b.top)
                    .map((row) => row.el)
                    .pop();
            }

            try {
                target.scrollIntoView({ block: 'center', inline: 'center' });
            } catch (e) {}
            target.click();
            return true;
        }""",
        {"selectors": selectors, "text_tokens": text_tokens or [], "prefer_last": prefer_last},
    )
    if clicked:
        step_delay(page, timeout_ms)
    return clicked


def click_cell_by_text(page, text: str, timeout_ms: int | None = None) -> bool:
    try:
        page.get_by_role("cell", name=text, exact=True).first.click(timeout=timeout_ms)
        step_delay(page, timeout_ms)
        return True
    except PlaywrightError:
        pass
    return click_visible_element_by_text(page, ["td", "a", "button", "[role='cell']"], [text], timeout_ms)


def click_next_button(page, config: dict, timeout_ms: int | None = None) -> None:
    workflow_cfg = config["epost"]["workflow"]
    next_cfg = workflow_cfg["shared"]["next_button"]
    preferred_selectors = next_cfg.get("preferred_selectors", [])
    for selector in preferred_selectors:
        if click_selector(page, selector, timeout_ms):
            return
    clicked = click_visible_element_by_text(
        page,
        next_cfg["selectors"],
        next_cfg["text_contains"],
        timeout_ms,
        prefer_last=True,
    )
    if not clicked:
        raise RuntimeError("다음 버튼을 찾지 못했습니다.")


def ensure_section_open(page, heading_text_contains: str, timeout_ms: int | None = None) -> bool:
    if not heading_text_contains:
        return False
    opened = page.evaluate(
        """(payload) => {
            const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
            const token = payload.token;
            const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'));
            const target = headings.find((h) => normalize(h.textContent).includes(token));
            if (!target) return false;
            const hasOn = target.classList && target.classList.contains('on');
            if (!hasOn) {
                target.scrollIntoView({ block: 'center', inline: 'center' });
                target.click();
            }
            return true;
        }""",
        {"token": heading_text_contains},
    )
    if opened:
        step_delay(page, timeout_ms)
    return opened


def remove_modal_and_login(page, config: dict, timeout_ms: int | None = None) -> dict:
    epost_cfg = config["epost"]
    script_cfg = epost_cfg["script"]
    # 로그인 단계에서만 사용하는 설정(Working process 이전)
    login_cfg = script_cfg["login"]
    creds = script_cfg["credentials"]
    payload = {
        "modal_selector": login_cfg["modal_selector"],
        "id_selectors": login_cfg["id_selectors"],
        "pw_selectors": login_cfg["password_selectors"],
        "username": creds["username"],
        "password": creds["password"],
    }
    result = page.evaluate(
        """(payload) => {
            const modal = document.querySelector(payload.modal_selector);
            if (modal) {
                modal.style.display = 'none';
                modal.remove();
            }

            const selectFirst = (selectors) => {
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) return el;
                }
                return null;
            };

            const idInput = selectFirst(payload.id_selectors);
            const pwInput = selectFirst(payload.pw_selectors);

            if (idInput) {
                idInput.value = payload.username;
                idInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
            if (pwInput) {
                pwInput.value = payload.password;
                pwInput.dispatchEvent(new Event('input', { bubbles: true }));
            }

            let submitted = false;
            if (typeof checkVal === 'function') {
                checkVal();
                submitted = true;
            } else {
                const form = document.querySelector('#frmLogin');
                if (form) {
                    form.submit();
                    submitted = true;
                }
            }

            return {
                id_found: !!idInput,
                pw_found: !!pwInput,
                submitted,
            };
        }""",
        payload,
    )
    step_delay(page, timeout_ms)
    return result


def attach_dialog_handler(page, accept_contains: list[str]) -> None:
    def _handler(dialog) -> None:
        message = dialog.message
        if any(token in message for token in accept_contains):
            dialog.accept()
        else:
            dialog.dismiss()

    page.on("dialog", _handler)


def attach_popup_closer(context, url_contains: list[str], timeout_ms: int) -> None:
    def _handler(popup) -> None:
        try:
            popup.wait_for_load_state(timeout=timeout_ms)
        except PlaywrightTimeoutError:
            pass
        if any(token in popup.url for token in url_contains):
            popup.close()

    context.on("page", _handler)


def navigate_to_parcel_reservation(page, config: dict, timeout_ms: int | None = None) -> None:
    workflow_cfg = config["epost"]["workflow"]
    nav_cfg = workflow_cfg["shared"]["navigation"]
    for step_cfg in nav_cfg["menu_steps"]:
        clicked = click_link_by_text_index(
            page,
            step_cfg["text"],
            step_cfg.get("index", 0),
            step_cfg.get("container_selector"),
            timeout_ms,
        )
        if not clicked:
            raise RuntimeError(f"메뉴 링크를 찾지 못했습니다: {step_cfg['text']}")


def toggle_address_popup_trigger(
    page, config: dict, click: bool, timeout_ms: int | None = None, target: str = "sender"
) -> bool:
    epost_cfg = config["epost"]
    workflow_cfg = epost_cfg["workflow"]
    popup_cfg = workflow_cfg["shared"]["address_popup"]
    onclick_contains = None
    trigger_map = popup_cfg.get("trigger_onclick_contains_by_target", {})
    if isinstance(trigger_map, dict):
        onclick_contains = trigger_map.get(target)
    if not onclick_contains:
        onclick_contains = popup_cfg.get("trigger_onclick_contains")
    payload = {
        "click": click,
        "onclick_contains": onclick_contains,
        "text_contains": popup_cfg.get("trigger_text_contains"),
        "require_visible": True,
    }
    clicked = page.evaluate(
        """(payload) => {
            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };
            const pickMatch = (matches) => {
                if (!matches.length) return null;
                const visible = matches.find(isVisible);
                if (visible) return visible;
                return payload.require_visible ? null : matches[0];
            };
            const findLink = () => {
                if (payload.onclick_contains) {
                    const matches = Array.from(document.querySelectorAll('a')).filter(
                        (link) => (link.getAttribute('onclick') || '').includes(payload.onclick_contains)
                    );
                    const match = pickMatch(matches);
                    if (match) return match;
                }
                if (payload.text_contains) {
                    const matches = Array.from(document.querySelectorAll('a')).filter(
                        (link) => (link.textContent || '').includes(payload.text_contains)
                    );
                    const match = pickMatch(matches);
                    if (match) return match;
                }
                return null;
            };

            const link = findLink();
            if (!link) return false;
            if (payload.click) link.click();
            return true;
        }""",
        payload,
    )
    if clicked and click:
        step_delay(page, timeout_ms)
    return clicked


def open_address_popup(page, config: dict, timeout_ms: int, target: str = "sender"):
    epost_cfg = config["epost"]
    workflow_cfg = epost_cfg["workflow"]
    # target에 따라 적절한 step config 선택
    step_key = "step_01_sender" if target == "sender" else "step_03_recipient"
    step_cfg = workflow_cfg.get(step_key, {})
    heading = step_cfg.get("heading_text_contains")
    if heading:
        ensure_section_open(page, heading, timeout_ms)

    popup_timeout_ms = epost_cfg["script"]["timeouts_ms"]["popup"]
    if not toggle_address_popup_trigger(page, config, False, timeout_ms=timeout_ms, target=target):
        raise RuntimeError("주소찾기 링크를 찾지 못했습니다.")

    try:
        with page.expect_popup(timeout=popup_timeout_ms) as popup_info:
            toggle_address_popup_trigger(page, config, True, timeout_ms, target=target)
        return popup_info.value
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("주소찾기 팝업이 열리지 않았습니다.") from exc


def fill_address_popup(page, config: dict, timeout_ms: int) -> None:
    epost_cfg = config["epost"]
    workflow_cfg = epost_cfg["workflow"]
    popup_cfg = workflow_cfg["shared"]["address_popup"]
    keyword_selector = popup_cfg["keyword_selector"]
    page.locator(keyword_selector).fill(popup_cfg["keyword"])
    step_delay(page, timeout_ms)
    clicked = click_visible_element_by_text(
        page,
        popup_cfg.get("search_button_selectors", []),
        popup_cfg.get("search_button_text_contains", []),
        timeout_ms,
    )
    if not clicked:
        page.locator(keyword_selector).press("Enter")
        step_delay(page, timeout_ms)
    page.wait_for_timeout(timeout_ms)

    found = page.evaluate(
        """(payload) => {
            const normalize = (text) => (text || '').replace(/\\s+/g, '').trim();
            const tokens = (payload.tokens || []).filter(Boolean);
            const normalizedTokens = tokens.map(normalize).filter(Boolean);
            const links = Array.from(document.querySelectorAll('a'));

            const target = links.find((link) => {
                const text = link.textContent || '';
                const normalized = normalize(text);
                return normalizedTokens.some((token) => normalized.includes(token));
            }) || links.find((link) => {
                const text = link.textContent || '';
                return tokens.some((token) => text.includes(token));
            });

            if (!target) return false;
            target.click();
            return true;
        }""",
        {"tokens": [popup_cfg.get("result_text_contains"), popup_cfg.get("keyword")]},
    )
    if found:
        step_delay(page, timeout_ms)
    if not found:
        raise RuntimeError("주소 검색 결과를 찾지 못했습니다.")

    building = popup_cfg.get("building")
    unit = popup_cfg.get("unit")
    detail_address = normalize_spaces(str(popup_cfg.get("detail_address") or "")).strip()
    if building and unit:
        apartment_radio_name = popup_cfg.get("apartment_detail_radio_name")
        if apartment_radio_name:
            try:
                page.get_by_role("radio", name=apartment_radio_name, exact=True).check(timeout=timeout_ms)
            except PlaywrightError:
                pass
            step_delay(page, timeout_ms)

        building_field_name = popup_cfg.get("building_field_name", "동")
        unit_field_name = popup_cfg.get("unit_field_name", "호")
        filled = False
        try:
            page.get_by_role("textbox", name=building_field_name, exact=True).fill(building, timeout=timeout_ms)
            page.get_by_role("textbox", name=unit_field_name, exact=True).fill(unit, timeout=timeout_ms)
            filled = True
        except PlaywrightError:
            filled = False
        if not filled:
            page.evaluate(
                """(payload) => {
                    const setValue = (token, value) => {
                        const candidates = Array.from(document.querySelectorAll('input[type=\"text\"], input[type=\"tel\"], textarea'));
                        const matchesToken = (el) => {
                            const attrs = [
                                el.getAttribute('aria-label') || '',
                                el.getAttribute('title') || '',
                                el.getAttribute('name') || '',
                                el.getAttribute('id') || '',
                                el.getAttribute('placeholder') || '',
                            ];
                            return attrs.some((attr) => attr.includes(token));
                        };
                        const el = candidates.find(matchesToken);
                        if (!el) return false;
                        el.value = value;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    };
                    setValue(payload.buildingToken, payload.building);
                    setValue(payload.unitToken, payload.unit);
                }""",
                {
                    "buildingToken": building_field_name,
                    "unitToken": unit_field_name,
                    "building": building,
                    "unit": unit,
                },
            )
        step_delay(page, timeout_ms)
    elif detail_address:
        label_tokens = popup_cfg.get("detail_address_label_contains") or ["상세주소"]
        if isinstance(label_tokens, str):
            label_tokens = [label_tokens]
        if not isinstance(label_tokens, list):
            label_tokens = ["상세주소"]
        label_tokens = [
            normalize_spaces(str(token)).strip()
            for token in label_tokens
            if normalize_spaces(str(token)).strip()
        ]
        if not label_tokens:
            label_tokens = ["상세주소"]
        if not set_input_by_associated_text_tokens(
            page, label_tokens, detail_address, timeout_ms
        ):
            raise RuntimeError("주소 팝업 상세주소 입력 필드를 찾지 못했습니다.")

    clicked = page.evaluate(
        """(text) => {
            const links = Array.from(document.querySelectorAll('a'));
            const target = links.find(link => (link.textContent || '').includes(text));
            if (!target) return false;
            target.click();
            return true;
        }""",
        popup_cfg["submit_text_contains"],
    )
    if clicked:
        step_delay(page, timeout_ms)
    if not clicked:
        raise RuntimeError("주소 팝업 입력 버튼을 찾지 못했습니다.")


def open_address_book_popup(page, config: dict, timeout_ms: int):
    epost_cfg = config["epost"]
    workflow_cfg = epost_cfg["workflow"]
    recipient_cfg = workflow_cfg.get("step_03_recipient", {})
    recipient_heading = recipient_cfg.get("heading_text_contains")
    if recipient_heading:
        ensure_section_open(page, recipient_heading, timeout_ms)
    address_book_cfg = recipient_cfg.get("address_book", {})
    popup_timeout_ms = epost_cfg["script"]["timeouts_ms"]["popup"]
    try:
        with page.expect_popup(timeout=popup_timeout_ms) as popup_info:
            clicked = click_link_by_text(page, address_book_cfg["search_text"], timeout_ms=timeout_ms)
        if not clicked:
            raise RuntimeError("주소록 검색 링크를 찾지 못했습니다.")
        return popup_info.value
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("주소록 팝업이 열리지 않았습니다.") from exc


def fill_item_info_fields(page, config: dict, timeout_ms: int | None = None) -> None:
    workflow_cfg = config["epost"]["workflow"]
    parcel_cfg = workflow_cfg["step_02_pickup_info"]
    item_info_cfg = workflow_cfg["step_04_item_info"]

    weight_selectors = parcel_cfg.get("weight_selectors")
    if not isinstance(weight_selectors, list) or not weight_selectors:
        weight_selectors = [parcel_cfg.get("weight_selector"), "#limit_wg", "#tmpWght1"]
    volume_selectors = parcel_cfg.get("volume_selectors")
    if not isinstance(volume_selectors, list) or not volume_selectors:
        volume_selectors = [parcel_cfg.get("volume_selector"), "#limit_vol", "#tmpVol1"]
    product_selectors = parcel_cfg.get("product_code_selectors")
    if not isinstance(product_selectors, list) or not product_selectors:
        product_selectors = [parcel_cfg.get("product_code_selector"), "#labProductCode"]

    if not set_select_value_any(page, weight_selectors, parcel_cfg.get("weight_code"), timeout_ms):
        raise RuntimeError("중량 선택 필드를 찾지 못했습니다.")
    if not set_select_value_any(page, volume_selectors, parcel_cfg.get("volume_code"), timeout_ms):
        raise RuntimeError("크기 선택 필드를 찾지 못했습니다.")
    if not set_select_value_any(page, product_selectors, parcel_cfg.get("product_code"), timeout_ms):
        raise RuntimeError("내용물코드 선택 필드를 찾지 못했습니다.")

    contents = item_info_cfg.get("contents_text") or item_info_cfg.get("item_selection_text")
    if contents:
        contents_selectors = [item_info_cfg.get("contents_selector"), "#labcont"]
        if not set_input_value_any(page, contents_selectors, contents, timeout_ms):
            raise RuntimeError("내용물 입력 필드를 찾지 못했습니다.")


def fill_delivery_note(page, config: dict, timeout_ms: int | None = None) -> None:
    workflow_cfg = config["epost"]["workflow"]
    item_info_cfg = workflow_cfg["step_04_item_info"]
    note = item_info_cfg.get("delivery_note")
    if not note:
        return
    selectors = item_info_cfg.get("delivery_note_selectors", [])
    for selector in selectors:
        if set_input_value(page, selector, note, timeout_ms):
            return
    if set_input_by_label_tokens(page, item_info_cfg.get("delivery_note_label_contains", []), note, timeout_ms):
        return
    raise RuntimeError("배송시 특이사항 입력 필드를 찾지 못했습니다.")


def handle_item_info_step_04(page, config: dict, timeouts: dict) -> None:
    workflow_cfg = config["epost"]["workflow"]
    item_cfg = workflow_cfg.get("step_04_item_info", {})
    item_heading = item_cfg.get("heading_text_contains")
    if item_heading:
        ensure_section_open(page, item_heading, timeouts["action"])

    fill_item_info_fields(page, config, timeouts["action"])
    fill_delivery_note(page, config, timeouts["action"])
    add_to_recipient_list(page, config, timeouts["action"])


def add_to_recipient_list(page, config: dict, timeout_ms: int | None = None) -> None:
    workflow_cfg = config["epost"]["workflow"]
    item_cfg = workflow_cfg.get("step_04_item_info", {})
    item_heading = item_cfg.get("heading_text_contains")
    if item_heading:
        ensure_section_open(page, item_heading, timeout_ms)
    add_button_text = item_cfg.get("add_to_list_button_text", "받는 분 목록에 추가")
    clicked = click_link_by_text(page, add_button_text, timeout_ms=timeout_ms)
    if not clicked:
        raise RuntimeError("받는 분 목록에 추가 링크를 찾지 못했습니다.")


def validate_address(page, config: dict, timeout_ms: int | None = None) -> None:
    workflow_cfg = config["epost"]["workflow"]
    recipient_list_cfg = workflow_cfg.get("step_05_recipient_list", {})
    recipient_list_heading = recipient_list_cfg.get("heading_text_contains")
    if recipient_list_heading:
        ensure_section_open(page, recipient_list_heading, timeout_ms)
    validation_button = recipient_list_cfg.get("address_validation_button_text", "주소검증")
    clicked = click_link_by_text(page, validation_button, timeout_ms=timeout_ms)
    if not clicked:
        raise RuntimeError("주소검증 링크를 찾지 못했습니다.")


def handle_payment_step_06(page, config: dict, timeouts: dict) -> None:
    workflow_cfg = config["epost"]["workflow"]
    payment_cfg = workflow_cfg.get("step_06_payment", {})
    payment_heading = payment_cfg.get("heading_text_contains")
    if payment_heading:
        if not ensure_section_open(page, payment_heading, timeouts["action"]):
            raise RuntimeError("결제수단 등록 섹션을 찾지 못했습니다.")

    payment_cfg = workflow_cfg["step_06_payment"]
    selectors_cfg = payment_cfg.get("selectors", {})
    field_selectors = selectors_cfg.get("fields", {})

    card_numbers = payment_cfg.get("card_numbers") or []
    if len(card_numbers) < 4:
        raise RuntimeError("결제 카드번호 설정이 올바르지 않습니다.")

    expiry = payment_cfg.get("expiry") or []
    if len(expiry) < 2:
        raise RuntimeError("결제 카드 유효기간 설정이 올바르지 않습니다.")

    password_digits = payment_cfg.get("password_digits") or []
    if len(password_digits) < 2:
        raise RuntimeError("결제 카드 비밀번호(앞 2자리) 설정이 올바르지 않습니다.")

    birthdate = payment_cfg.get("birthdate")
    if not birthdate:
        raise RuntimeError("결제 카드 생년월일 설정이 비어 있습니다.")

    if not set_input_value(page, field_selectors.get("card_no1", "#creditNo1"), card_numbers[0], timeouts["action"]):
        raise RuntimeError("카드번호(1) 입력 필드를 찾지 못했습니다.")
    if not set_input_value(page, field_selectors.get("card_no2", "#creditNo2"), card_numbers[1], timeouts["action"]):
        raise RuntimeError("카드번호(2) 입력 필드를 찾지 못했습니다.")
    if not set_input_value(page, field_selectors.get("card_no3", "#creditNo3"), card_numbers[2], timeouts["action"]):
        raise RuntimeError("카드번호(3) 입력 필드를 찾지 못했습니다.")
    if not set_input_value(page, field_selectors.get("card_no4", "#creditNo4"), card_numbers[3], timeouts["action"]):
        raise RuntimeError("카드번호(4) 입력 필드를 찾지 못했습니다.")

    if not set_input_value(
        page, field_selectors.get("expiry_month", "#creditExp1"), expiry[0], timeouts["action"]
    ):
        raise RuntimeError("유효기간(월) 입력 필드를 찾지 못했습니다.")
    if not set_input_value(page, field_selectors.get("expiry_year", "#creditExp2"), expiry[1], timeouts["action"]):
        raise RuntimeError("유효기간(년) 입력 필드를 찾지 못했습니다.")

    if not set_input_value(
        page, field_selectors.get("password_digit1", "#creditPwd1"), password_digits[0], timeouts["action"]
    ):
        raise RuntimeError("비밀번호(1) 입력 필드를 찾지 못했습니다.")
    if not set_input_value(
        page, field_selectors.get("password_digit2", "#creditPwd2"), password_digits[1], timeouts["action"]
    ):
        raise RuntimeError("비밀번호(2) 입력 필드를 찾지 못했습니다.")

    if not set_input_value(page, field_selectors.get("birthdate", "#creditBirth"), birthdate, timeouts["action"]):
        raise RuntimeError("생년월일 입력 필드를 찾지 못했습니다.")

    receipt_choice = str(payment_cfg.get("mobile_receipt") or "").strip().lower()
    receipt_selectors = (selectors_cfg.get("mobile_receipt") or {}) if isinstance(selectors_cfg, dict) else {}
    if receipt_choice in {"y", "yes", "true", "1"}:
        set_checkbox_checked(page, receipt_selectors.get("yes", "#mreceipt_y"), True, timeouts["action"])
        set_checkbox_checked(page, receipt_selectors.get("no", "#mreceipt_n"), False, timeouts["action"])
    elif receipt_choice in {"n", "no", "false", "0"}:
        set_checkbox_checked(page, receipt_selectors.get("no", "#mreceipt_n"), True, timeouts["action"])
        set_checkbox_checked(page, receipt_selectors.get("yes", "#mreceipt_y"), False, timeouts["action"])

    validate_selector = selectors_cfg.get("validate_button", "#certCreditInfo")
    if click_selector(page, validate_selector, timeouts["action"]):
        return

    clicked = page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            try { el.scrollIntoView({ block: 'center', inline: 'center' }); } catch (e) {}
            el.click();
            return true;
        }""",
        validate_selector,
    )
    if clicked:
        step_delay(page, timeouts["action"])
        return

    invoked = page.evaluate(
        """() => {
            if (typeof certCreditInfo === 'function') {
                certCreditInfo();
                return true;
            }
            return false;
        }"""
    )
    if invoked:
        step_delay(page, timeouts["action"])
        return
    raise RuntimeError("결제카드검증 버튼을 클릭하지 못했습니다.")


def address_book_is_empty(page, empty_tokens: list[str]) -> bool:
    if not empty_tokens:
        return False
    return page.evaluate(
        """(tokens) => {
            const bodyText = document.body ? (document.body.innerText || '') : '';
            return tokens.some(token => bodyText.includes(token));
        }""",
        empty_tokens,
    )


def fill_sender_section(page, config: dict, timeouts: dict) -> None:
    workflow_cfg = config["epost"]["workflow"]
    sender_cfg = workflow_cfg["step_01_sender"]
    sender_name = normalize_spaces(str(sender_cfg.get("name") or "")).strip()
    page2 = open_address_popup(page, config, timeouts["action"], target="sender")
    attach_dialog_handler(page2, config["epost"]["script"]["login"]["accept_dialog_contains"])
    fill_address_popup(page2, config, timeouts["action"])
    step_delay(page2, timeouts["action"])
    try:
        page2.close()
    except PlaywrightError:
        pass
    if sender_name:
        selector_fields = (sender_cfg.get("selectors") or {}).get("fields") or {}
        name_selector = selector_fields.get("name")
        updated = False
        if name_selector:
            updated = set_input_value(page, name_selector, sender_name, timeouts["action"])
        if not updated:
            label_tokens = sender_cfg.get("name_label_contains") or ["이름"]
            if isinstance(label_tokens, str):
                label_tokens = [label_tokens]
            if not isinstance(label_tokens, list) or not label_tokens:
                label_tokens = ["이름"]
            label_tokens = [str(token) for token in label_tokens if str(token).strip()]
            if not set_input_by_associated_text_tokens(page, label_tokens, sender_name, timeouts["action"]):
                raise RuntimeError("보내는 분 이름 입력 필드를 찾지 못했습니다.")
    set_input_value(
        page,
        sender_cfg["phone_selectors"]["middle"],
        sender_cfg["phone"]["middle"],
        timeouts["action"],
    )
    set_input_value(
        page,
        sender_cfg["phone_selectors"]["last"],
        sender_cfg["phone"]["last"],
        timeouts["action"],
    )


def fill_manual_recipient(page, config: dict, timeouts: dict) -> None:
    epost_cfg = config["epost"]
    workflow_cfg = epost_cfg["workflow"]
    recipient_cfg = workflow_cfg["step_03_recipient"]
    selector_fields = (recipient_cfg.get("selectors") or {}).get("fields") or {}
    name_selector = selector_fields.get("name", 'input[name="receiverName"]')
    detail_addr_selector = selector_fields.get("detail_address", 'input[name="reDetailAddr"]')
    phone_1_selector = selector_fields.get("phone_1", "#reCell1")
    phone_2_selector = selector_fields.get("phone_2", "#reCell2")
    phone_3_selector = selector_fields.get("phone_3", "#reCell3")

    set_input_value(page, name_selector, recipient_cfg["name"], timeouts["action"])
    page2 = open_address_popup(page, config, timeouts["action"], target="recipient")
    fill_address_popup(page2, config, timeouts["action"])
    step_delay(page2, timeouts["action"])
    page2.close()
    set_input_value(page, detail_addr_selector, recipient_cfg["detail_address"], timeouts["action"])
    phone_parts = recipient_cfg["phone"]["mobile"]
    set_input_value(page, phone_1_selector, phone_parts[0], timeouts["action"])
    set_input_value(page, phone_2_selector, phone_parts[1], timeouts["action"])
    set_input_value(page, phone_3_selector, phone_parts[2], timeouts["action"])


def login_epost_once(page, config: dict, timeouts: dict) -> str:
    epost_cfg = config["epost"]
    script_cfg = epost_cfg["script"]
    page.goto(script_cfg["urls"]["login"], wait_until="domcontentloaded")
    page.wait_for_timeout(timeouts["page_stabilize"])

    login_result = remove_modal_and_login(page, config, timeouts["action"])
    if not login_result["id_found"] or not login_result["pw_found"]:
        raise RuntimeError("로그인 입력창을 찾지 못했습니다.")
    if not login_result["submitted"]:
        raise RuntimeError("로그인 제출에 실패했습니다.")

    try:
        page.wait_for_url("**/main.retrieveMainPage.comm", timeout=timeouts["login_wait"])
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("로그인 완료 페이지로 이동하지 못했습니다.") from exc
    step_delay(page, timeouts["action"])
    return canonicalize_url(page.url)


def open_parcel_reservation_page(page, config: dict, timeouts: dict, main_page_url: str | None) -> None:
    epost_cfg = config["epost"]
    script_cfg = epost_cfg["script"]

    if main_page_url:
        page.goto(main_page_url, wait_until="domcontentloaded")
        page.wait_for_timeout(timeouts["page_stabilize"])
        navigate_to_parcel_reservation(page, config, timeouts["action"])
        page.wait_for_timeout(timeouts["page_stabilize"])
        if "parcel.epost.go.kr" in (page.url or ""):
            return

    page.goto(script_cfg["urls"]["parcel_reservation"], wait_until="domcontentloaded")
    page.wait_for_timeout(timeouts["page_stabilize"])
    if "parcel.epost.go.kr" not in (page.url or ""):
        raise RuntimeError("택배 예약 페이지로 이동하지 못했습니다.")


def run_parcel_reservation_flow(
    page,
    config: dict,
    timeouts: dict,
    progress_dir: Path,
    run_until_step_int: int | None,
    target_slug: str,
) -> tuple[str, dict[str, dict[str, str]]]:
    workflow_cfg = config["epost"]["workflow"]
    artifacts: dict[str, dict[str, str]] = {}

    agree_text = workflow_cfg["step_00_initial"]["agree_checkbox_text"]
    checked = page.evaluate(
        """(text) => {
            const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
            for (const checkbox of checkboxes) {
                const container = checkbox.closest('label') || checkbox.parentElement;
                const labelText = container ? container.textContent || '' : '';
                if (labelText.includes(text)) {
                    if (!checkbox.checked) checkbox.click();
                    return true;
                }
            }
            const fallback = document.querySelector('input[type="checkbox"]');
            if (fallback && !fallback.checked) {
                fallback.click();
                return true;
            }
            return false;
        }""",
        agree_text,
    )
    if checked:
        step_delay(page, timeouts["action"])
    if not checked:
        raise RuntimeError("필수 확인 체크박스를 선택하지 못했습니다.")

    fill_sender_section(page, config, timeouts)
    step01_artifacts = write_success_artifacts(page, progress_dir, prefix=f"post_test_step01_sender_filled_{target_slug}")
    if step01_artifacts:
        artifacts["step01_sender_filled"] = {
            "screenshot": str(step01_artifacts[0]),
            "snapshot": str(step01_artifacts[1]),
        }
    if run_until_step_int == 1:
        partial_artifacts = write_success_artifacts(page, progress_dir, prefix=f"post_test_partial_step01_{target_slug}")
        if partial_artifacts:
            artifacts["partial_step01"] = {
                "screenshot": str(partial_artifacts[0]),
                "snapshot": str(partial_artifacts[1]),
            }
        return "partial_step01", artifacts
    click_next_button(page, config, timeouts["action"])

    parcel_cfg = workflow_cfg["step_02_pickup_info"]
    parcel_selectors_cfg = parcel_cfg.get("selectors") or {}
    parcel_field_selectors = parcel_selectors_cfg.get("fields") or {}

    if not set_select_value(
        page,
        parcel_field_selectors.get("wish_receipt_date", 'select[name="wishReceiptTime"]'),
        parcel_cfg["wish_receipt_date"],
        timeouts["action"],
    ):
        raise RuntimeError("방문일 선택 필드를 찾지 못했습니다.")
    if not set_select_value(
        page,
        parcel_field_selectors.get("wish_receipt_time", 'select[name="wishReceiptTimeNm"]'),
        parcel_cfg["wish_receipt_time"],
        timeouts["action"],
    ):
        raise RuntimeError("방문시간 선택 필드를 찾지 못했습니다.")
    if not set_select_value(
        page,
        parcel_field_selectors.get("pickup_keep", 'select[name="pickupKeep"]'),
        parcel_cfg["pickup_keep_code"],
        timeouts["action"],
    ):
        raise RuntimeError("보관방법 선택 필드를 찾지 못했습니다.")
    set_input_value(
        page,
        parcel_field_selectors.get("pickup_keep_note", 'input[name="pickupKeepNm"]'),
        parcel_cfg["pickup_keep_note"],
        timeouts["action"],
    )

    weight_selectors = parcel_cfg.get("weight_selectors")
    if not isinstance(weight_selectors, list) or not weight_selectors:
        weight_selectors = [parcel_cfg.get("weight_selector"), "#limit_wg", "#tmpWght1"]
    volume_selectors = parcel_cfg.get("volume_selectors")
    if not isinstance(volume_selectors, list) or not volume_selectors:
        volume_selectors = [parcel_cfg.get("volume_selector"), "#limit_vol", "#tmpVol1"]
    product_selectors = parcel_cfg.get("product_code_selectors")
    if not isinstance(product_selectors, list) or not product_selectors:
        product_selectors = [parcel_cfg.get("product_code_selector"), "#labProductCode"]

    set_select_value_any(
        page,
        weight_selectors,
        parcel_cfg.get("weight_code"),
        timeouts["action"],
    )
    set_select_value_any(
        page,
        volume_selectors,
        parcel_cfg.get("volume_code"),
        timeouts["action"],
    )
    set_select_value_any(
        page,
        product_selectors,
        parcel_cfg.get("product_code"),
        timeouts["action"],
    )

    pickup_save_selector = (parcel_selectors_cfg.get("buttons") or {}).get("pickup_save", "#pickupSaveBtn")
    click_selector(page, pickup_save_selector, timeouts["action"])
    if run_until_step_int == 2:
        partial_artifacts = write_success_artifacts(page, progress_dir, prefix=f"post_test_partial_step02_{target_slug}")
        if partial_artifacts:
            artifacts["partial_step02"] = {
                "screenshot": str(partial_artifacts[0]),
                "snapshot": str(partial_artifacts[1]),
            }
        return "partial_step02", artifacts
    pickup_next_cfg = parcel_selectors_cfg.get("next") or {}
    pickup_next_container = pickup_next_cfg.get("container_selector", "#pickupInfoDiv")
    pickup_next_text = pickup_next_cfg.get("text", "다음")
    if not click_link_by_text(page, pickup_next_text, pickup_next_container, timeouts["action"]):
        raise RuntimeError("방문접수 소포정보 다음 버튼을 찾지 못했습니다.")

    recipient_cfg = workflow_cfg["step_03_recipient"]
    if not recipient_cfg["use_address_book"]:
        raise RuntimeError("주소록 사용이 비활성화되어 있습니다.")
    address_book_cfg = recipient_cfg.get("address_book", {})
    page4 = open_address_book_popup(page, config, timeouts["action"])
    group_selectors = (address_book_cfg.get("selectors") or {}).get("group_selectors")
    if not isinstance(group_selectors, list) or not group_selectors:
        group_selectors = ["select"]
    if not set_select_value_any(page4, group_selectors, recipient_cfg["address_book_group_value"], timeouts["action"]):
        page4.locator("select").first.select_option(recipient_cfg["address_book_group_value"])
    step_delay(page4, timeouts["action"])
    page4.on("dialog", accept_dialog_safely)
    if not click_link_by_text(page4, address_book_cfg["confirm_text"], timeout_ms=timeouts["action"]):
        page4.close()
        raise RuntimeError("주소록 확인 링크를 찾지 못했습니다.")
    step_delay(page4, timeouts["action"])
    page4.wait_for_load_state("domcontentloaded")
    if address_book_is_empty(page4, address_book_cfg["empty_text_contains"]):
        page4.close()
        raise RuntimeError("주소록이 비어 있습니다.")
    recipient_name = recipient_cfg["name"]
    recipient_selector_fields = (recipient_cfg.get("selectors") or {}).get("fields") or {}
    receiver_name_selector = recipient_selector_fields.get("name", 'input[name="receiverName"]')
    receiver_check_arg = {"selector": receiver_name_selector, "token": recipient_name}

    def _wait_receiver_applied(check_arg: dict, timeout_ms: int) -> bool:
        try:
            page.wait_for_function(
                """(payload) => {
                    const el = document.querySelector(payload.selector);
                    if (!el) return false;
                    const v = (el.value || '').toString();
                    return v.includes(payload.token);
                }""",
                arg=check_arg,
                timeout=timeout_ms,
            )
            return True
        except PlaywrightTimeoutError:
            return False

    applied = False
    for attempt in range(3):
        if hasattr(page4, "is_closed") and page4.is_closed():
            break
        if attempt == 0:
            try:
                page4.get_by_role("link", name=recipient_name, exact=True).first.click(timeout=timeouts["popup"])
                clicked = True
            except PlaywrightError:
                clicked = False
        elif attempt == 1:
            try:
                page4.locator("a", has_text=recipient_name).first.click(timeout=timeouts["popup"])
                clicked = True
            except PlaywrightError:
                clicked = False
        else:
            try:
                clicked = bool(
                    page4.evaluate(
                        """(token) => {
                            const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                            const isVisible = (el) => {
                                if (!el) return false;
                                const style = window.getComputedStyle(el);
                                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                                const rect = el.getBoundingClientRect();
                                return rect.width > 0 && rect.height > 0;
                            };
                            const links = Array.from(document.querySelectorAll('a')).filter(isVisible);
                            const target = links.find((a) => normalize(a.textContent).includes(token));
                            if (!target) return false;
                            target.click();
                            return true;
                        }""",
                        recipient_name,
                    )
                )
            except PlaywrightError:
                clicked = False

        if not clicked:
            continue

        step_delay(page4, timeouts["action"])
        applied = _wait_receiver_applied(
            receiver_check_arg,
            timeouts["popup"],
        )
        if applied:
            break

    if not applied:
        raise RuntimeError("받는 분 정보가 메인 페이지에 적용되지 않았습니다.")

    try:
        if hasattr(page4, "is_closed") and page4.is_closed():
            pass
        else:
            page4.close()
    except PlaywrightError:
        pass

    click_next_button(page, config, timeouts["action"])

    handle_item_info_step_04(page, config, timeouts)
    click_next_button(page, config, timeouts["action"])

    recipient_list_cfg = workflow_cfg["step_05_recipient_list"]
    recipient_list_selectors = recipient_list_cfg.get("selectors") or {}
    list_buttons = recipient_list_selectors.get("buttons") or {}
    img_btn_selector = list_buttons.get("img_btn", "#imgBtn")
    addr_btn_selector = list_buttons.get("addr_btn", "#btnAddr")
    click_selector(page, img_btn_selector, timeouts["action"])
    click_selector(page, addr_btn_selector, timeouts["action"])
    list_next_cfg = recipient_list_selectors.get("next") or {}
    list_next_container = list_next_cfg.get("container_selector", "#recListNextDiv")
    list_next_text = list_next_cfg.get("text", "다음")
    if not click_link_by_text(page, list_next_text, list_next_container, timeouts["action"]):
        raise RuntimeError("받는 분 목록 다음 버튼을 찾지 못했습니다.")

    step_delay(page, timeouts["action"])

    handle_payment_step_06(page, config, timeouts)
    step_delay(page, timeouts["action"])

    success_artifacts = write_success_artifacts(page, progress_dir, prefix=f"post_test_success_{target_slug}")
    if success_artifacts:
        artifacts["success"] = {
            "screenshot": str(success_artifacts[0]),
            "snapshot": str(success_artifacts[1]),
        }
    return "success", artifacts


def write_batch_summary(progress_dir: Path, results: list[dict[str, object]]) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary_path = progress_dir / f"post_test_batch_summary_{timestamp}.json"
    payload = {"timestamp": timestamp, "results": results}
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


def run(playwright: Playwright) -> None:
    config = load_config()
    epost_cfg = config["epost"]
    script_cfg = epost_cfg["script"]
    workflow_cfg = epost_cfg["workflow"]
    # script_cfg: 기본 스크립트 설정 / workflow_cfg: 로그인 이후 작업(working process)
    timeouts = script_cfg["timeouts_ms"]
    progress_dir = ROOT / script_cfg["paths"]["progress_dir"]
    ensure_progress_dir(progress_dir)
    keep_open_after_run = script_cfg["browser"].get("keep_open_after_run", False)
    keep_open_poll_ms = timeouts.get("keep_open_poll_ms", 1000)
    run_until_step = workflow_cfg.get("run_until_step")
    try:
        run_until_step_int = int(run_until_step) if run_until_step is not None else None
    except (TypeError, ValueError):
        run_until_step_int = None

    targets = get_excel_targets(config)
    if not targets:
        raise ValueError("config.yaml의 input_excel.targets 또는 input_excel.filter.*.value 설정이 필요합니다.")

    df, excel_path, sheet_name, mgmt_col, name_col = load_subject_dataframe_from_excel(config)

    browser = playwright.chromium.launch(
        headless=script_cfg["browser"]["headless"],
        args=script_cfg["browser"]["args"],
    )
    context = browser.new_context()
    permissions = script_cfg["browser"].get("permissions", [])
    permission_origins = script_cfg["browser"].get("permissions_origins", [])
    if permissions:
        if permission_origins:
            for origin in permission_origins:
                context.grant_permissions(permissions, origin=origin)
        else:
            context.grant_permissions(permissions)
    attach_popup_closer(context, script_cfg["popups"]["close_url_contains"], timeouts["popup"])
    login_page = context.new_page()
    attach_dialog_handler(login_page, script_cfg["login"]["accept_dialog_contains"])

    page_for_manual_close = login_page
    error: Exception | None = None
    results: list[dict[str, object]] = []
    try:
        main_page_url = login_epost_once(login_page, config, timeouts)

        for idx, target in enumerate(targets, start=1):
            mgmt_value = target["management_no"]
            name_value = target["subject_name"]
            target_slug = (
                f"{idx:03d}_{safe_filename_token(mgmt_value, max_len=20)}_{safe_filename_token(name_value, max_len=20)}"
            )
            print(f"[{idx}/{len(targets)}] start: 관리번호={mgmt_value} / 이름={name_value}")

            page = context.new_page()
            page_for_manual_close = page
            attach_dialog_handler(page, script_cfg["login"]["accept_dialog_contains"])
            try:
                open_parcel_reservation_page(page, config, timeouts, main_page_url)

                row = load_subject_row_from_dataframe(
                    df,
                    mgmt_col,
                    name_col,
                    mgmt_value,
                    name_value,
                    excel_path,
                    sheet_name,
                )
                apply_excel_overrides(config, row=row, target=target)
                validate_excel_overrides_applied(config, target=target)

                status, artifacts = run_parcel_reservation_flow(
                    page,
                    config,
                    timeouts,
                    progress_dir,
                    run_until_step_int,
                    target_slug,
                )
                results.append(
                    {
                        "index": idx,
                        "management_no": mgmt_value,
                        "subject_name": name_value,
                        "status": status,
                        "artifacts": artifacts,
                    }
                )
                print(f"[{idx}/{len(targets)}] done: {status}")
            except Exception as exc:
                failure_prefix = script_cfg["paths"]["failure_screenshot_prefix"]
                failure_artifacts = write_success_artifacts(page, progress_dir, prefix=f"{failure_prefix}_{target_slug}")
                artifacts: dict[str, dict[str, str]] = {}
                if failure_artifacts:
                    artifacts["failure"] = {
                        "screenshot": str(failure_artifacts[0]),
                        "snapshot": str(failure_artifacts[1]),
                    }
                results.append(
                    {
                        "index": idx,
                        "management_no": mgmt_value,
                        "subject_name": name_value,
                        "status": "failure",
                        "error": str(exc),
                        "artifacts": artifacts,
                    }
                )
                print(f"[{idx}/{len(targets)}] failed: {exc}")
            finally:
                if keep_open_after_run and idx == len(targets):
                    continue
                try:
                    page.close()
                except PlaywrightError:
                    pass

        summary_path = write_batch_summary(progress_dir, results)
        print(f"Batch summary saved: {summary_path}")

        failed = [row for row in results if row.get("status") == "failure"]
        if failed:
            raise RuntimeError(f"일부 대상자 실패: {len(failed)}건 (summary={summary_path})")
        print("Batch completed successfully!")
    except Exception as exc:
        error = exc
    finally:
        wait_for_manual_close(page_for_manual_close, keep_open_after_run, keep_open_poll_ms)
        context.close()
        browser.close()
    if error:
        raise error


def main() -> None:
    with sync_playwright() as playwright:
        run(playwright)


if __name__ == "__main__":
    main()
