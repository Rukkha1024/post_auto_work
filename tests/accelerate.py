import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://is.kdca.go.kr/")
    page.locator("#base").content_frame.get_by_role("link", name="공동인증서 로그인", exact=True).click()
    page.locator("#base").content_frame.get_by_role("textbox", name="인증서 암호").click()
    page.locator("#base").content_frame.get_by_text("은행개인").click()
    page.locator("#base").content_frame.get_by_role("textbox", name="인증서 암호").click()
    page.locator("#base").content_frame.get_by_role("textbox", name="인증서 암호").fill("qhrtns0504@")
    page.locator("#base").content_frame.get_by_role("button", name="확인").click()
    page.locator("#base").content_frame.locator("#contents").get_by_text("시스템을 선택해주세요 국건영통합(22년오픈)").click()
    page.locator("#base").content_frame.get_by_role("link", name="국건영통합(22년오픈)").click()
    page.locator("#base").content_frame.get_by_role("link", name="건강설문조사관리").click()
    page.locator("#base").content_frame.get_by_role("link", name="가속도계관리").click()
    page.locator("#base").content_frame.get_by_role("link", name=" 가속도계지급관리").click()
    page.locator("#base").content_frame.locator("iframe[name=\"ifrm\"]").content_frame.locator("select[name=\"weekOrdn\"]").select_option("1")
    page.locator("#base").content_frame.locator("iframe[name=\"ifrm\"]").content_frame.get_by_role("link", name="조회").click()
    page.locator("#base").content_frame.locator("iframe[name=\"ifrm\"]").content_frame.locator("select[name=\"exmnYr\"]").select_option("2025")
    page.locator("#base").content_frame.locator("iframe[name=\"ifrm\"]").content_frame.locator("select[name=\"weekOrdn\"]").select_option("1")
    with page.expect_popup() as page1_info:
        page.locator("#base").content_frame.locator("iframe[name=\"ifrm\"]").content_frame.get_by_role("link", name="엑셀 다운로드").click()
    page1 = page1_info.value
    page1.get_by_role("textbox", name="여기에 사유를 입력하세요").click()
    page1.get_by_role("textbox", name="여기에 사유를 입력하세요").fill("ddfdf")
    page1.close()
    page.locator("#base").content_frame.locator("iframe[name=\"ifrm\"]").content_frame.get_by_role("link", name="조회").click()
    with page.expect_popup() as page2_info:
        page.locator("#base").content_frame.locator("iframe[name=\"ifrm\"]").content_frame.get_by_role("link", name="엑셀 다운로드").click()
    page2 = page2_info.value
    page2.get_by_role("textbox", name="여기에 사유를 입력하세요").click()
    page2.get_by_role("textbox", name="여기에 사유를 입력하세요").fill("fdf")
    page2.get_by_role("link", name="닫기").click()
    page2.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
