from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import post_test as pt  # noqa: E402


def md5_json(obj: object) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def main() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "pickup_address_rule_expected.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"Invalid fixture: {fixture_path}")

    actual_outputs: list[dict[str, object]] = []
    expected_outputs: list[dict[str, object]] = []

    for idx, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Case #{idx} must be a dict")
        input_text = case.get("input")
        expected = case.get("expected")
        if not isinstance(input_text, str) or not isinstance(expected, dict):
            raise ValueError(f"Case #{idx} must include input(str) and expected(dict)")

        parsed = pt.parse_pickup_address_rule(input_text)
        actual = {
            "keyword": parsed.get("keyword"),
            "result_text_contains": parsed.get("result_text_contains"),
            "detail_address": parsed.get("detail_address"),
            "building": parsed.get("building"),
            "unit": parsed.get("unit"),
        }

        if actual != expected:
            raise AssertionError(
                f"Mismatch case #{idx}\n"
                f"- input: {input_text!r}\n"
                f"- expected: {expected!r}\n"
                f"- actual: {actual!r}\n"
            )

        actual_outputs.append(actual)
        expected_outputs.append(expected)

    actual_md5 = md5_json(actual_outputs)
    expected_md5 = md5_json(expected_outputs)
    if actual_md5 != expected_md5:
        raise AssertionError(
            "MD5 mismatch between new outputs and reference file\n"
            f"- actual:   {actual_md5}\n"
            f"- expected: {expected_md5}\n"
        )

    config = pt.load_config()
    juso_cfg = ((config.get("epost") or {}).get("script") or {}).get("juso_api") or {}
    if isinstance(juso_cfg, dict) and juso_cfg.get("enabled", False):
        sample_jibun = "서울특별시 중구 태평로1가 31"
        enriched = pt.parse_pickup_address(sample_jibun, config)
        token = str(enriched.get("result_text_contains") or "")
        if not pt.looks_like_road_token(token):
            raise AssertionError(
                "Juso fallback did not produce a road-like token.\n"
                f"- input: {sample_jibun!r}\n"
                f"- result_text_contains: {token!r}\n"
            )

    print(f"OK: {len(cases)} cases (md5={actual_md5})")


if __name__ == "__main__":
    main()
