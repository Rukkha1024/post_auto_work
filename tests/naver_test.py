import re
import os
import yaml
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright, expect


def load_config():
    """YAML 설정 파일 로드"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_credentials_from_excel():
    """
    Excel 파일에서 subject로 필터링하여 주소와 착용날짜를 반환
    설정은 config.yaml과 환경변수에서 관리

    Returns:
        (주소, 착용날짜) 튜플
    """
    import polars as pl

    # 설정 로드
    config = load_config()

    # 환경변수로 subject 오버라이드 가능
    target_subject = os.getenv(
        "NAVER_TEST_SUBJECT",
        config['target']['subject']
    )

    # Excel 경로 구성
    excel_path = Path(__file__).parent.parent / config['excel']['path']
    sheet_name = config['excel']['sheet_name']
    columns = config['excel']['columns']

    # Excel 파일 읽기
    df = pl.read_excel(str(excel_path), sheet_name=sheet_name)

    # subject 필터링
    filtered = df.filter(pl.col(columns['subject']) == target_subject)

    if filtered.height == 0:
        raise ValueError(
            f"'{target_subject}'에 해당하는 데이터를 찾을 수 없습니다. "
            f"Excel 파일: {excel_path}, 시트: {sheet_name}"
        )

    # 첫 번째 매치 사용
    row = filtered.row(0, named=True)
    return row[columns['username']], row[columns['password']]


def run(playwright: Playwright) -> None:
    # Excel에서 인증 정보 로드
    username, password = load_credentials_from_excel()

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.naver.com/")
    page.get_by_role("link", name="NAVER 로그인").click()
    page.get_by_role("textbox", name="아이디 또는 전화번호").click()
    page.get_by_role("textbox", name="아이디 또는 전화번호").fill(username)
    page.get_by_role("textbox", name="아이디 또는 전화번호").press("Tab")
    page.get_by_role("button", name="삭제").press("Tab")
    page.get_by_role("textbox", name="비밀번호").fill(password)
    page.get_by_role("button", name="로그인").click()
    page.get_by_role("tab", name="메일 999+").click()
    page.get_by_role("tab", name="카페").click()
    page.get_by_role("tab", name="블로그").click()
    page.get_by_role("button", name="다음", exact=True).click()
    page.get_by_role("tab", name="MYBOX").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
