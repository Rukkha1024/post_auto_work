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
    process_cfg = config["epost"]["working_process"]
    next_cfg = process_cfg["next_button"]
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
    process_cfg = config["epost"]["working_process"]
    nav_cfg = process_cfg["navigation"]
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
    process_cfg = epost_cfg["working_process"]
    popup_cfg = process_cfg["address_popup"]
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
    process_cfg = epost_cfg["working_process"]
    sections_cfg = process_cfg.get("sections", {})
    heading = sections_cfg.get(target, {}).get("heading_text_contains")
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

    building = popup_cfg.get("building")
    unit = popup_cfg.get("unit")
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
    sections_cfg = process_cfg.get("sections", {})
    recipient_heading = sections_cfg.get("recipient", {}).get("heading_text_contains")
    if recipient_heading:
        ensure_section_open(page, recipient_heading, timeout_ms)
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


def open_item_info_popup(page, config: dict, timeout_ms: int):
    epost_cfg = config["epost"]
    process_cfg = epost_cfg["working_process"]
    item_info_cfg = process_cfg["item_info"]
    sections_cfg = process_cfg.get("sections", {})
    item_heading = sections_cfg.get("item_info", {}).get("heading_text_contains")
    if item_heading:
        ensure_section_open(page, item_heading, timeout_ms)
    popup_timeout_ms = epost_cfg["script"]["timeouts_ms"]["popup"]
    trigger_text = item_info_cfg["popup_trigger_text"]
    if page.get_by_text(trigger_text).count() == 0:
        raise RuntimeError("물품정보 불러오기 트리거를 찾지 못했습니다.")
    try:
        with page.expect_popup(timeout=popup_timeout_ms) as popup_info:
            page.get_by_text(trigger_text).first.click(timeout=timeout_ms)
        return popup_info.value
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("물품정보 팝업이 열리지 않았습니다.") from exc


def select_item_in_popup(page, item_text: str, timeout_ms: int | None = None) -> None:
    clicked = click_cell_by_text(page, item_text, timeout_ms=timeout_ms)
    if not clicked:
        raise RuntimeError("물품정보 팝업에서 품목을 찾지 못했습니다.")
    step_delay(page, timeout_ms)
    try:
        if hasattr(page, "is_closed") and page.is_closed():
            return
        page.close()
    except PlaywrightError:
        pass


def fill_delivery_note(page, config: dict, timeout_ms: int | None = None) -> None:
    process_cfg = config["epost"]["working_process"]
    item_info_cfg = process_cfg["item_info"]
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


def add_to_recipient_list(page, config: dict, timeout_ms: int | None = None) -> None:
    process_cfg = config["epost"]["working_process"]
    sections_cfg = process_cfg.get("sections", {})
    item_heading = sections_cfg.get("item_info", {}).get("heading_text_contains")
    if item_heading:
        ensure_section_open(page, item_heading, timeout_ms)
    recipient_list_cfg = process_cfg["recipient_list"]
    clicked = click_link_by_text(page, recipient_list_cfg["add_button_text"], timeout_ms=timeout_ms)
    if not clicked:
        raise RuntimeError("받는 분 목록에 추가 링크를 찾지 못했습니다.")


def validate_address(page, config: dict, timeout_ms: int | None = None) -> None:
    process_cfg = config["epost"]["working_process"]
    sections_cfg = process_cfg.get("sections", {})
    recipient_list_heading = sections_cfg.get("recipient_list", {}).get("heading_text_contains")
    if recipient_list_heading:
        ensure_section_open(page, recipient_list_heading, timeout_ms)
    validation_cfg = process_cfg["address_validation"]
    clicked = click_link_by_text(page, validation_cfg["button_text"], timeout_ms=timeout_ms)
    if not clicked:
        raise RuntimeError("주소검증 링크를 찾지 못했습니다.")


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
    process_cfg = config["epost"]["working_process"]
    sender_cfg = process_cfg["sender"]
    page2 = open_address_popup(page, config, timeouts["action"], target="sender")
    attach_dialog_handler(page2, config["epost"]["script"]["login"]["accept_dialog_contains"])
    fill_address_popup(page2, config, timeouts["action"])
    step_delay(page2, timeouts["action"])
    try:
        page2.close()
    except PlaywrightError:
        pass
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
    process_cfg = epost_cfg["working_process"]
    recipient_cfg = process_cfg["recipient"]
    set_input_value(page, 'input[name="receiverName"]', recipient_cfg["name"], timeouts["action"])
    page2 = open_address_popup(page, config, timeouts["action"], target="recipient")
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
    keep_open_after_run = script_cfg["browser"].get("keep_open_after_run", False)
    keep_open_poll_ms = timeouts.get("keep_open_poll_ms", 1000)

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
    page = context.new_page()
    attach_dialog_handler(page, script_cfg["login"]["accept_dialog_contains"])

    error: Exception | None = None
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

        navigate_to_parcel_reservation(page, config, timeouts["action"])
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

        fill_sender_section(page, config, timeouts)
        click_next_button(page, config, timeouts["action"])

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
        if not click_link_by_text(page, "다음", "#pickupInfoDiv", timeouts["action"]):
            raise RuntimeError("방문접수 소포정보 다음 버튼을 찾지 못했습니다.")

        recipient_cfg = process_cfg["recipient"]
        if not recipient_cfg["use_address_book"]:
            raise RuntimeError("주소록 사용이 비활성화되어 있습니다.")
        address_book_cfg = process_cfg["address_book"]
        page4 = open_address_book_popup(page, config, timeouts["action"])
        page4.locator("select").first.select_option(recipient_cfg["address_book_group_value"])
        step_delay(page4, timeouts["action"])
        page4.on("dialog", dismiss_dialog_safely)
        if not click_link_by_text(page4, address_book_cfg["confirm_text"], timeout_ms=timeouts["action"]):
            page4.close()
            raise RuntimeError("주소록 확인 링크를 찾지 못했습니다.")
        step_delay(page4, timeouts["action"])
        page4.wait_for_load_state("domcontentloaded")
        if address_book_is_empty(page4, address_book_cfg["empty_text_contains"]):
            page4.close()
            raise RuntimeError("주소록이 비어 있습니다.")
        recipient_name = recipient_cfg["name"]
        receiver_check_arg = {"selector": 'input[name="receiverName"]', "token": recipient_name}

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
                clicked = click_cell_by_text(page4, recipient_name, timeout_ms=timeouts["action"])
            elif attempt == 1:
                clicked = click_link_by_text(page4, recipient_name, timeout_ms=timeouts["action"])
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
                min(timeouts["popup"], 5000) if attempt == 0 else timeouts["popup"],
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

        item_info_cfg = process_cfg["item_info"]
        page_item = open_item_info_popup(page, config, timeouts["action"])
        page_item.once("dialog", lambda dialog: dialog.dismiss())
        select_item_in_popup(page_item, item_info_cfg["item_selection_text"], timeouts["action"])
        fill_delivery_note(page, config, timeouts["action"])
        click_next_button(page, config, timeouts["action"])

        add_to_recipient_list(page, config, timeouts["action"])

        validate_address(page, config, timeouts["action"])

        click_selector(page, "#imgBtn", timeouts["action"])
        click_selector(page, "#btnAddr", timeouts["action"])
        if not click_link_by_text(page, "다음", "#recListNextDiv", timeouts["action"]):
            raise RuntimeError("받는 분 목록 다음 버튼을 찾지 못했습니다.")

        step_delay(page, timeouts["action"])

        print("Test completed successfully!")
    except Exception as exc:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_name = f"{script_cfg['paths']['failure_screenshot_prefix']}_{timestamp}.png"
        screenshot_path = progress_dir / screenshot_name
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass
        error = exc
    finally:
        wait_for_manual_close(page, keep_open_after_run, keep_open_poll_ms)
        context.close()
        browser.close()
    if error:
        raise error


with sync_playwright() as playwright:
    run(playwright)
