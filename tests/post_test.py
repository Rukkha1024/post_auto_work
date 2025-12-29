# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from pathlib import Path

import yaml
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PlaywrightTimeoutError


ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    config_path = ROOT / "config.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def ensure_progress_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def set_input_value(page, selector: str, value: str) -> bool:
    if value is None:
        return False
    return page.evaluate(
        """(sel, val) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""",
        selector,
        value,
    )


def set_select_value(page, selector: str, value: str) -> bool:
    if value is None:
        return False
    return page.evaluate(
        """(sel, val) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            el.value = val;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""",
        selector,
        value,
    )


def click_selector(page, selector: str) -> bool:
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            el.click();
            return true;
        }""",
        selector,
    )


def click_link_by_text(page, text: str, container_selector: str | None = None) -> bool:
    return page.evaluate(
        """(payload) => {
            const root = payload.container ? document.querySelector(payload.container) : document;
            if (!root) return false;
            const links = Array.from(root.querySelectorAll('a'));
            const target = links.find(link => (link.textContent || '').includes(payload.text));
            if (!target) return false;
            target.click();
            return true;
        }""",
        {"text": text, "container": container_selector},
    )


def remove_modal_and_login(page, config: dict) -> dict:
    login_cfg = config["epost"]["login"]
    creds = config["epost"]["credentials"]
    payload = {
        "modal_selector": login_cfg["modal_selector"],
        "id_selectors": login_cfg["id_selectors"],
        "pw_selectors": login_cfg["password_selectors"],
        "username": creds["username"],
        "password": creds["password"],
    }
    return page.evaluate(
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


def toggle_address_popup_trigger(page, config: dict, click: bool) -> bool:
    popup_cfg = config["epost"]["address_popup"]
    payload = {
        "click": click,
        "onclick_contains": popup_cfg["trigger_onclick_contains"],
        "text_contains": popup_cfg["trigger_text_contains"],
    }
    return page.evaluate(
        """(payload) => {
            const findLink = () => {
                if (payload.onclick_contains) {
                    const match = Array.from(document.querySelectorAll('a')).find(
                        (link) => (link.getAttribute('onclick') || '').includes(payload.onclick_contains)
                    );
                    if (match) return match;
                }
                if (payload.text_contains) {
                    const match = Array.from(document.querySelectorAll('a')).find(
                        (link) => (link.textContent || '').includes(payload.text_contains)
                    );
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


def open_address_popup(page, config: dict, timeout_ms: int):
    if not toggle_address_popup_trigger(page, config, False):
        raise RuntimeError("주소찾기 링크를 찾지 못했습니다.")

    try:
        with page.expect_popup(timeout=timeout_ms) as popup_info:
            toggle_address_popup_trigger(page, config, True)
        return popup_info.value
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("주소찾기 팝업이 열리지 않았습니다.") from exc


def fill_address_popup(page, config: dict, timeout_ms: int) -> None:
    popup_cfg = config["epost"]["address_popup"]
    page.locator('input[name="keyword"]').fill(popup_cfg["keyword"])
    page.locator('button[type="button"]').first.click()
    page.wait_for_timeout(timeout_ms)

    found = page.evaluate(
        """(text) => {
            const links = Array.from(document.querySelectorAll('a'));
            const target = links.find(link => (link.textContent || '').includes(text));
            if (!target) return false;
            target.click();
            return true;
        }""",
        popup_cfg["result_text_contains"],
    )
    if not found:
        raise RuntimeError("주소 검색 결과를 찾지 못했습니다.")

    page.evaluate(
        """(payload) => {
            const inputs = Array.from(document.querySelectorAll('input[type="text"]'));
            for (const input of inputs) {
                if (input.placeholder && input.placeholder.includes('동')) {
                    input.value = payload.building;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                } else if (input.placeholder && input.placeholder.includes('호')) {
                    input.value = payload.unit;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
        }""",
        {"building": popup_cfg["building"], "unit": popup_cfg["unit"]},
    )

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
    if not clicked:
        raise RuntimeError("주소 팝업 입력 버튼을 찾지 못했습니다.")


def open_address_book_popup(page, timeout_ms: int):
    try:
        with page.expect_popup(timeout=timeout_ms) as popup_info:
            clicked = click_link_by_text(page, "주소록 검색")
        if not clicked:
            raise RuntimeError("주소록 검색 링크를 찾지 못했습니다.")
        return popup_info.value
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("주소록 팝업이 열리지 않았습니다.") from exc


def run(playwright: Playwright) -> None:
    config = load_config()
    epost_cfg = config["epost"]
    timeouts = epost_cfg["timeouts_ms"]

    progress_dir = ROOT / epost_cfg["paths"]["progress_dir"]
    ensure_progress_dir(progress_dir)

    browser = playwright.chromium.launch(
        headless=epost_cfg["browser"]["headless"],
        args=epost_cfg["browser"]["args"],
    )
    context = browser.new_context()
    attach_popup_closer(context, epost_cfg["popups"]["close_url_contains"], timeouts["popup"])
    page = context.new_page()
    attach_dialog_handler(page, epost_cfg["login"]["accept_dialog_contains"])

    try:
        page.goto(epost_cfg["urls"]["login"], wait_until="domcontentloaded")
        page.wait_for_timeout(timeouts["page_stabilize"])

        login_result = remove_modal_and_login(page, config)
        if not login_result["id_found"] or not login_result["pw_found"]:
            raise RuntimeError("로그인 입력창을 찾지 못했습니다.")
        if not login_result["submitted"]:
            raise RuntimeError("로그인 제출에 실패했습니다.")

        try:
            page.wait_for_url("**/main.retrieveMainPage.comm", timeout=timeouts["login_wait"])
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("로그인 완료 페이지로 이동하지 못했습니다.") from exc

        page.goto(epost_cfg["urls"]["parcel_reservation"], wait_until="domcontentloaded")
        page.wait_for_timeout(timeouts["page_stabilize"])

        agree_text = epost_cfg["parcel"]["agree_checkbox_text"]
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
        if not checked:
            raise RuntimeError("필수 확인 체크박스를 선택하지 못했습니다.")

        if not set_select_value(page, 'select[name="wishReceiptTime"]', epost_cfg["parcel"]["wish_receipt_date"]):
            raise RuntimeError("방문일 선택 필드를 찾지 못했습니다.")
        if not set_select_value(page, 'select[name="wishReceiptTimeNm"]', epost_cfg["parcel"]["wish_receipt_time"]):
            raise RuntimeError("방문시간 선택 필드를 찾지 못했습니다.")
        if not set_select_value(page, 'select[name="pickupKeep"]', epost_cfg["parcel"]["pickup_keep_code"]):
            raise RuntimeError("보관방법 선택 필드를 찾지 못했습니다.")
        set_input_value(page, 'input[name="pickupKeepNm"]', epost_cfg["parcel"]["pickup_keep_note"])

        set_select_value(page, "#tmpWght1", epost_cfg["parcel"]["weight_code"])
        set_select_value(page, "#tmpVol1", epost_cfg["parcel"]["volume_code"])
        set_select_value(page, "#labProductCode", epost_cfg["parcel"]["product_code"])

        click_selector(page, "#pickupSaveBtn")
        click_link_by_text(page, "다음", "#pickupInfoDiv")

        recipient_cfg = epost_cfg["recipient"]
        if recipient_cfg["use_address_book"]:
            page4 = open_address_book_popup(page, timeouts["popup"])
            page4.locator("select").first.select_option(recipient_cfg["address_book_group_value"])
            click_link_by_text(page4, "확인")
            page4.once("dialog", lambda dialog: dialog.dismiss())
            click_link_by_text(page4, recipient_cfg["name"])
            page4.close()
        else:
            set_input_value(page, 'input[name="receiverName"]', recipient_cfg["name"])
            page2 = open_address_popup(page, config, timeouts["popup"])
            fill_address_popup(page2, config, timeouts["action"])
            page2.close()
            set_input_value(page, 'input[name="reDetailAddr"]', recipient_cfg["detail_address"])
            phone_parts = recipient_cfg["phone"]["mobile"]
            set_input_value(page, "#reCell1", phone_parts[0])
            set_input_value(page, "#reCell2", phone_parts[1])
            set_input_value(page, "#reCell3", phone_parts[2])

        click_selector(page, "#imgBtn")
        click_selector(page, "#btnAddr")
        click_link_by_text(page, "다음", "#recListNextDiv")

        card_cfg = epost_cfg["payment"]
        card_numbers = card_cfg["card_numbers"]
        set_input_value(page, "#creditNo1", card_numbers[0])
        set_input_value(page, "#creditNo2", card_numbers[1])
        set_input_value(page, "#creditNo3", card_numbers[2])
        set_input_value(page, "#creditNo4", card_numbers[3])

        expiry = card_cfg["expiry"]
        set_input_value(page, "#creditExp1", expiry[0])
        set_input_value(page, "#creditExp2", expiry[1])

        pwd_digits = card_cfg["password_digits"]
        set_input_value(page, "#creditPwd1", pwd_digits[0])
        set_input_value(page, "#creditPwd2", pwd_digits[1])
        set_input_value(page, "#creditBirth", card_cfg["birthdate"])

        page.once("dialog", lambda dialog: dialog.dismiss())
        click_selector(page, "#certCreditInfo")
        page.wait_for_timeout(timeouts["action"])

        print("Test completed successfully!")
    except Exception:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_name = f"{epost_cfg['paths']['failure_screenshot_prefix']}_{timestamp}.png"
        screenshot_path = progress_dir / screenshot_name
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass
        raise
    finally:
        context.close()
        browser.close()


with sync_playwright() as playwright:
    run(playwright)
