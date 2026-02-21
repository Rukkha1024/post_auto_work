import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.epost.go.kr/usr/login/cafzc008k01.jsp?s_url=https://www.epost.go.kr")
    page.get_by_role("link", name="국내소포").nth(1).click()
    page.get_by_role("link", name="방문접수소포 반품예약").nth(2).click()
    page.get_by_role("link", name="menu").click()
    page.get_by_role("link", name="방문접수소포 방문접수예약").click()
    page.get_by_role("checkbox", name="우편금지물품·취급제한품목 및 손해배상 안내 확인").check()
    with page.expect_popup() as page2_info:
        page.get_by_role("link", name="주소찾기").click()
    page2 = page2_info.value
    page2.get_by_role("textbox", name="검색어입력").click()
    page2.get_by_role("textbox", name="검색어입력").fill("향군로 74번길 26")
    page2.get_by_role("textbox", name="검색어입력").press("Enter")
    page2.get_by_role("button", name="검색").click()
    page2.get_by_role("link", name="충청북도 청주시 청원구 향군로74번길 26").click()
    page2.get_by_role("textbox", name="동").click()
    page2.get_by_role("textbox", name="동").fill("103")
    page2.get_by_role("textbox", name="호", exact=True).click()
    page2.get_by_role("textbox", name="호", exact=True).fill("912")
    page2.get_by_role("link", name="주소입력").click()
    page2.close()
    page.get_by_title("보내는 분의 휴대전화 중간자리").click()
    page.get_by_title("보내는 분의 휴대전화 중간자리").press("ArrowRight")
    page.get_by_title("보내는 분의 휴대전화 중간자리").press("ArrowRight")
    page.get_by_title("보내는 분의 휴대전화 중간자리").press("ArrowRight")
    page.get_by_title("보내는 분의 휴대전화 중간자리").fill("3532")
    page.get_by_title("보내는 분의 휴대전화 뒷자리").click()
    page.get_by_title("보내는 분의 휴대전화 뒷자리").click()
    page.get_by_title("보내는 분의 휴대전화 뒷자리").press("ArrowRight")
    page.get_by_title("보내는 분의 휴대전화 뒷자리").press("ArrowRight")
    page.get_by_title("보내는 분의 휴대전화 뒷자리").fill("1342")
    page.get_by_role("link", name="다음").click()
    page.get_by_label("방문접수일자").select_option("2026-01-02")
    page.locator("#pickupKeep").select_option("05")
    page.get_by_role("textbox", name="보관장소 입력").click()
    page.get_by_role("textbox", name="보관장소 입력").fill("문 앞에 있어요")
    page.locator("#pickupInfoDiv").get_by_role("paragraph").filter(has_text="다음").click()
    page.locator("#pickupInfoDiv").get_by_role("link", name="다음").click()
    with page.expect_popup() as page3_info:
        page.get_by_role("link", name="주소록 검색").click()
    page3 = page3_info.value
    page3.get_by_label("그룹조건").select_option("0")
    page3.get_by_role("link", name="확인").click()
    page3.once("dialog", lambda dialog: dialog.dismiss())
    page3.get_by_role("link", name="육지연").click()
    page3.close()
    page.get_by_role("link", name="다음").nth(2).click()
    with page.expect_popup() as page4_info:
        page.get_by_text("물품정보 불러오기").click()
    page4 = page4_info.value
    page4.once("dialog", lambda dialog: dialog.dismiss())
    page4.get_by_role("link", name="전자제품", exact=True).click()
    page4.close()
    page.get_by_role("textbox", name="배송시 특이사항").fill("없을 시 010-3532-1342로 연락바랍니다. ")
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
