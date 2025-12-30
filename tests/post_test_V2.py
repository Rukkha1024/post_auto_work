import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.epost.go.kr/usr/login/cafzc008k01.jsp?s_url=https://www.epost.go.kr")
    page.get_by_role("link", name="방문접수소포 예약").nth(1).click()
    page.get_by_role("img", name="펼치기/접기").nth(1).click()
    page.get_by_label("방문접수일자").select_option("2026-01-05")
    page.locator("#pickupKeep").select_option("05")
    page.get_by_role("textbox", name="보관장소 입력").click()
    page.get_by_role("textbox", name="보관장소 입력").fill("please get in door ")
    page.get_by_role("img", name="펼치기/접기").nth(2).click()
    page.get_by_role("img", name="펼치기/접기").nth(3).click()
    page.locator("#mainForm").get_by_role("img", name="펼치기/접기").click()
    with page.expect_popup() as page2_info:
        page.get_by_role("link", name="주소록 검색").click()
    page2 = page2_info.value
    page2.get_by_label("그룹조건").select_option("0")
    page2.get_by_role("link", name="확인").click()
    page2.once("dialog", lambda dialog: dialog.dismiss())
    page2.get_by_role("link", name="육지연").click()
    page2.close()
    page.get_by_role("link", name="다음").nth(2).click()
    with page.expect_popup() as page3_info:
        page.get_by_text("물품정보 불러오기").click()
    page3 = page3_info.value
    page3.once("dialog", lambda dialog: dialog.dismiss())
    page3.get_by_role("link", name="전자제품", exact=True).click()
    page3.close()
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("link", name="받는 분 목록에 추가").click()
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("link", name="주소검증").click()
    page.locator("#recListNextDiv").get_by_role("link", name="다음").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
