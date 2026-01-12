from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

import post_test as pt


def export_pickup_address_parsing_csv(config: dict) -> Path:
    df, excel_path, sheet_name, management_no_col, subject_name_col = (
        pt.load_subject_dataframe_from_excel(config)
    )

    pickup_col = str(((config.get("input_excel") or {}).get("columns") or {}).get("pickup_address") or "").strip()
    if not pickup_col:
        raise ValueError("config.yaml의 input_excel.columns.pickup_address 설정이 비어 있습니다.")

    script_cfg = (config.get("epost") or {}).get("script") or {}
    paths_cfg = script_cfg.get("paths") if isinstance(script_cfg, dict) else {}
    progress_dir = str((paths_cfg or {}).get("progress_dir") or "progress").strip() or "progress"
    out_dir = pt.resolve_repo_path(progress_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    juso_cfg = script_cfg.get("juso_api") if isinstance(script_cfg, dict) else {}
    juso_cfg = juso_cfg if isinstance(juso_cfg, dict) else {}
    juso_mode = str(juso_cfg.get("mode") or "if_needed").strip().lower() or "if_needed"

    records: list[dict[str, object]] = []
    for row_index, row in enumerate(df.iter_rows(named=True), start=1):
        pickup_cell = row.get(pickup_col)
        pickup_source = pt.normalize_spaces(str(pickup_cell or "")).strip()
        if not pickup_source:
            continue

        rule = pt.parse_pickup_address_rule(pickup_source)
        final = pt.parse_pickup_address(pickup_source, config)

        rule_token = str(rule.get("result_text_contains") or "").strip()
        final_token = str(final.get("result_text_contains") or "").strip()

        records.append(
            {
                "row_index": row_index,
                "management_no": str(row.get(management_no_col) or "").strip(),
                "subject_name": str(row.get(subject_name_col) or "").strip(),
                "pickup_address_source": pickup_source,
                "pickup_address_clean": str(rule.get("raw") or "").strip() or None,
                "keyword_rule": str(rule.get("keyword") or "").strip() or None,
                "result_text_contains_rule": rule_token or None,
                "detail_address_rule": rule.get("detail_address"),
                "building_rule": rule.get("building"),
                "unit_rule": rule.get("unit"),
                "keyword_final": str(final.get("keyword") or "").strip() or None,
                "result_text_contains_final": final_token or None,
                "detail_address_final": final.get("detail_address"),
                "building_final": final.get("building"),
                "unit_final": final.get("unit"),
                "rule_token_road_like": pt.looks_like_road_token(rule_token),
                "final_token_road_like": pt.looks_like_road_token(final_token),
                "api_checked": final.get("api_checked"),
                "api_hit": final.get("api_hit"),
                "api_adjusted": final.get("api_adjusted"),
                "api_error": final.get("api_error"),
                "juso_mode": juso_mode,
                "excel_path": str(excel_path),
                "sheet_name": str(sheet_name),
                "pickup_col": pickup_col,
            }
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"pickup_address_parsing_{stamp}.csv"
    schema_overrides = {
        "row_index": pl.Int64,
        "management_no": pl.Utf8,
        "subject_name": pl.Utf8,
        "pickup_address_source": pl.Utf8,
        "pickup_address_clean": pl.Utf8,
        "keyword_rule": pl.Utf8,
        "result_text_contains_rule": pl.Utf8,
        "detail_address_rule": pl.Utf8,
        "building_rule": pl.Utf8,
        "unit_rule": pl.Utf8,
        "keyword_final": pl.Utf8,
        "result_text_contains_final": pl.Utf8,
        "detail_address_final": pl.Utf8,
        "building_final": pl.Utf8,
        "unit_final": pl.Utf8,
        "rule_token_road_like": pl.Boolean,
        "final_token_road_like": pl.Boolean,
        "api_checked": pl.Boolean,
        "api_hit": pl.Boolean,
        "api_adjusted": pl.Boolean,
        "api_error": pl.Utf8,
        "juso_mode": pl.Utf8,
        "excel_path": pl.Utf8,
        "sheet_name": pl.Utf8,
        "pickup_col": pl.Utf8,
    }
    pl.DataFrame(
        records,
        infer_schema_length=0,
        schema_overrides=schema_overrides,
        strict=False,
    ).write_csv(out_path, include_bom=True)
    return out_path


def main() -> None:
    config = pt.load_config()
    out_path = export_pickup_address_parsing_csv(config)
    print(out_path)


if __name__ == "__main__":
    main()
