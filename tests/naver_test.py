import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.naver.com/")
    page.get_by_role("link", name="NAVER 로그인").click()
    page.get_by_role("textbox", name="아이디 또는 전화번호").click()
    page.get_by_role("textbox", name="아이디 또는 전화번호").fill("chocho9911")
    page.get_by_role("textbox", name="아이디 또는 전화번호").press("Tab")
    page.get_by_role("button", name="삭제").press("Tab")
    page.get_by_role("textbox", name="비밀번호").fill("ilikegoogle")
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
