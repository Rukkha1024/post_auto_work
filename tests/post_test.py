# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from pathlib import Path

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


def step_delay(page, timeout_ms: int | None) -> None:
    if timeout_ms and timeout_ms > 0:
        if hasattr(page, "is_closed") and page.is_closed():
            return
        try:
            page.wait_for_timeout(timeout_ms)
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
    updated = page.evaluate(
        """(payload) => {
            const el = document.querySelector(payload.selector);
            if (!el) return false;
            el.value = payload.value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""",
        {"selector": selector, "value": value},
    )
    if updated:
        step_delay(page, timeout_ms)
    return updated


def click_selector(page, selector: str, timeout_ms: int | None = None) -> bool:
    clicked = page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return false;
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
            const links = Array.from(root.querySelectorAll('a'));
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


def click_visible_element_by_text(
    page, selectors: list[str], text_tokens: list[str], timeout_ms: int | None = None
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
                return tokens.some(token => text.includes(token));
            };
            for (const selector of payload.selectors || []) {
                const elements = Array.from(document.querySelectorAll(selector));
                for (const el of elements) {
                    if (el.disabled) continue;
                    if (!isVisible(el)) continue;
                    if (!matchesText(el)) continue;
                    el.click();
                    return true;
                }
            }
            return false;
        }""",
        {"selectors": selectors, "text_tokens": text_tokens or []},
    )
    if clicked:
        step_delay(page, timeout_ms)
    return clicked


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


def toggle_address_popup_trigger(page, config: dict, click: bool, timeout_ms: int | None = None) -> bool:
    epost_cfg = config["epost"]
    process_cfg = epost_cfg["working_process"]
    popup_cfg = process_cfg["address_popup"]
    payload = {
        "click": click,
        "onclick_contains": popup_cfg["trigger_onclick_contains"],
        "text_contains": popup_cfg["trigger_text_contains"],
    }
    clicked = page.evaluate(
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
    if clicked and click:
        step_delay(page, timeout_ms)
    return clicked


def open_address_popup(page, config: dict, timeout_ms: int):
    script_cfg = config["epost"]["script"]
    popup_timeout_ms = script_cfg["timeouts_ms"]["popup"]
    if not toggle_address_popup_trigger(page, config, False):
        raise RuntimeError("주소찾기 링크를 찾지 못했습니다.")

    try:
        with page.expect_popup(timeout=popup_timeout_ms) as popup_info:
            toggle_address_popup_trigger(page, config, True, timeout_ms)
        return popup_info.value
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("주소찾기 팝업이 열리지 않았습니다.") from exc


def fill_address_popup(page, config: dict, timeout_ms: int) -> None:
    epost_cfg = config["epost"]
    process_cfg = epost_cfg["working_process"]
    popup_cfg = process_cfg["address_popup"]
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
        """(text) => {
            const links = Array.from(document.querySelectorAll('a'));
            const target = links.find(link => (link.textContent || '').includes(text));
            if (!target) return false;
            target.click();
            return true;
        }""",
        popup_cfg["result_text_contains"],
    )
    if found:
        step_delay(page, timeout_ms)
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
    step_delay(page, timeout_ms)

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
    process_cfg = epost_cfg["working_process"]
    address_book_cfg = process_cfg["address_book"]
    popup_timeout_ms = epost_cfg["script"]["timeouts_ms"]["popup"]
    try:
        with page.expect_popup(timeout=popup_timeout_ms) as popup_info:
            clicked = click_link_by_text(page, address_book_cfg["search_text"], timeout_ms=timeout_ms)
        if not clicked:
            raise RuntimeError("주소록 검색 링크를 찾지 못했습니다.")
        return popup_info.value
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("주소록 팝업이 열리지 않았습니다.") from exc


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


def fill_manual_recipient(page, config: dict, timeouts: dict) -> None:
    epost_cfg = config["epost"]
    process_cfg = epost_cfg["working_process"]
    recipient_cfg = process_cfg["recipient"]
    set_input_value(page, 'input[name="receiverName"]', recipient_cfg["name"], timeouts["action"])
    page2 = open_address_popup(page, config, timeouts["action"])
    fill_address_popup(page2, config, timeouts["action"])
    step_delay(page2, timeouts["action"])
    page2.close()
    set_input_value(page, 'input[name="reDetailAddr"]', recipient_cfg["detail_address"], timeouts["action"])
    phone_parts = recipient_cfg["phone"]["mobile"]
    set_input_value(page, "#reCell1", phone_parts[0], timeouts["action"])
    set_input_value(page, "#reCell2", phone_parts[1], timeouts["action"])
    set_input_value(page, "#reCell3", phone_parts[2], timeouts["action"])


def run(playwright: Playwright) -> None:
    config = load_config()
    epost_cfg = config["epost"]
    script_cfg = epost_cfg["script"]
    process_cfg = epost_cfg["working_process"]
    # script_cfg: 기본 스크립트 설정 / process_cfg: 로그인 이후 작업(working process)
    timeouts = script_cfg["timeouts_ms"]
    progress_dir = ROOT / script_cfg["paths"]["progress_dir"]
    ensure_progress_dir(progress_dir)

    browser = playwright.chromium.launch(
        headless=script_cfg["browser"]["headless"],
        args=script_cfg["browser"]["args"],
    )
    context = browser.new_context()
    attach_popup_closer(context, script_cfg["popups"]["close_url_contains"], timeouts["popup"])
    page = context.new_page()
    attach_dialog_handler(page, script_cfg["login"]["accept_dialog_contains"])

    try:
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

        page.goto(script_cfg["urls"]["parcel_reservation"], wait_until="domcontentloaded")
        page.wait_for_timeout(timeouts["page_stabilize"])

        agree_text = process_cfg["parcel"]["agree_checkbox_text"]
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

        if not set_select_value(
            page,
            'select[name="wishReceiptTime"]',
            process_cfg["parcel"]["wish_receipt_date"],
            timeouts["action"],
        ):
            raise RuntimeError("방문일 선택 필드를 찾지 못했습니다.")
        if not set_select_value(
            page,
            'select[name="wishReceiptTimeNm"]',
            process_cfg["parcel"]["wish_receipt_time"],
            timeouts["action"],
        ):
            raise RuntimeError("방문시간 선택 필드를 찾지 못했습니다.")
        if not set_select_value(
            page,
            'select[name="pickupKeep"]',
            process_cfg["parcel"]["pickup_keep_code"],
            timeouts["action"],
        ):
            raise RuntimeError("보관방법 선택 필드를 찾지 못했습니다.")
        set_input_value(
            page, 'input[name="pickupKeepNm"]', process_cfg["parcel"]["pickup_keep_note"], timeouts["action"]
        )

        set_select_value(page, "#tmpWght1", process_cfg["parcel"]["weight_code"], timeouts["action"])
        set_select_value(page, "#tmpVol1", process_cfg["parcel"]["volume_code"], timeouts["action"])
        set_select_value(page, "#labProductCode", process_cfg["parcel"]["product_code"], timeouts["action"])

        click_selector(page, "#pickupSaveBtn", timeouts["action"])
        click_link_by_text(page, "다음", "#pickupInfoDiv", timeouts["action"])

        recipient_cfg = process_cfg["recipient"]
        manual_entry_required = not recipient_cfg["use_address_book"]
        if recipient_cfg["use_address_book"]:
            address_book_cfg = process_cfg["address_book"]
            page4 = open_address_book_popup(page, config, timeouts["action"])
            page4.locator("select").first.select_option(recipient_cfg["address_book_group_value"])
            step_delay(page4, timeouts["action"])
            page4.get_by_text(address_book_cfg["confirm_text"]).first.click()
            step_delay(page4, timeouts["action"])
            page4.wait_for_load_state("domcontentloaded")
            page4.once("dialog", lambda dialog: dialog.dismiss())
            if address_book_is_empty(page4, address_book_cfg["empty_text_contains"]):
                manual_entry_required = True
                step_delay(page4, timeouts["action"])
                page4.close()
            else:
                name_locator = page4.get_by_text(recipient_cfg["name"])
                if name_locator.count() == 0:
                    manual_entry_required = True
                else:
                    name_locator.first.click()
                    step_delay(page4, timeouts["action"])
                page4.close()
        if manual_entry_required:
            fill_manual_recipient(page, config, timeouts)

        click_selector(page, "#imgBtn", timeouts["action"])
        click_selector(page, "#btnAddr", timeouts["action"])
        click_link_by_text(page, "다음", "#recListNextDiv", timeouts["action"])

        card_cfg = process_cfg["payment"]
        card_numbers = card_cfg["card_numbers"]
        set_input_value(page, "#creditNo1", card_numbers[0], timeouts["action"])
        set_input_value(page, "#creditNo2", card_numbers[1], timeouts["action"])
        set_input_value(page, "#creditNo3", card_numbers[2], timeouts["action"])
        set_input_value(page, "#creditNo4", card_numbers[3], timeouts["action"])

        expiry = card_cfg["expiry"]
        set_input_value(page, "#creditExp1", expiry[0], timeouts["action"])
        set_input_value(page, "#creditExp2", expiry[1], timeouts["action"])

        pwd_digits = card_cfg["password_digits"]
        set_input_value(page, "#creditPwd1", pwd_digits[0], timeouts["action"])
        set_input_value(page, "#creditPwd2", pwd_digits[1], timeouts["action"])
        set_input_value(page, "#creditBirth", card_cfg["birthdate"], timeouts["action"])

        click_selector(page, "#certCreditInfo", timeouts["action"])

        print("Test completed successfully!")
    except Exception:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_name = f"{script_cfg['paths']['failure_screenshot_prefix']}_{timestamp}.png"
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
