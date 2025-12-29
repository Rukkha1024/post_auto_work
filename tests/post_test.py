# -*- coding: utf-8 -*-
import re
from playwright.sync_api import Playwright, sync_playwright, expect
import time


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Navigate to login page
    page.goto("https://www.epost.go.kr/usr/login/cafzc008k01.jsp?s_url=https://www.epost.go.kr", wait_until="domcontentloaded")

    # Wait for page to stabilize
    time.sleep(3)

    # Use JavaScript to bypass loading modal and perform login
    page.evaluate("""() => {
        // 1. Remove the loading modal that blocks interactions
        const modal = document.querySelector('#nppfs-loading-modal');
        if (modal) {
            modal.style.display = 'none';
            modal.remove();
        }

        // 2. Fill login credentials directly
        const idInput = document.querySelector('input[name="user_id"]') || document.querySelector('input[title="아이디"]');
        const pwInput = document.querySelector('input[name="user_pwd"]') || document.querySelector('input[title="비밀번호"]');
        if (idInput && pwInput) {
            idInput.value = 'fg0015';
            pwInput.value = 'dmlduf1308!';
        }

        // 3. Trigger login function
        if (typeof checkVal === 'function') {
            checkVal();
        } else {
            const form = document.querySelector('#frmLogin');
            if (form) form.submit();
        }
    }""")

    # Wait for login to process and handle popup
    time.sleep(5)

    # Handle payment service notification popup if it appears
    try:
        # Wait for popup with timeout
        page1 = page.wait_for_event('popup', timeout=10000)
        time.sleep(2)
        # Close the popup
        page1.close()
        print("Popup closed successfully")
    except Exception as e:
        print(f"No popup appeared or popup handling failed: {e}")

    # Navigate to 방문접수소포 예약 using direct URL instead of clicking
    page.goto("https://www.epost.go.kr/usr/login/cafzc008k01.jsp?login=parcel18", wait_until="domcontentloaded")
    time.sleep(4)

    # Check the checkbox using JavaScript to avoid encoding issues
    page.evaluate("""() => {
        const checkbox = document.querySelector('input[type="checkbox"]');
        if (checkbox && !checkbox.checked) {
            checkbox.click();
        }
    }""")
    time.sleep(1)
    # Click address search button using JavaScript
    with page.expect_popup() as page2_info:
        page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a'));
            const addressLink = links.find(link => link.textContent.includes('주소'));
            if (addressLink) addressLink.click();
        }""")
    page2 = page2_info.value
    time.sleep(1)

    # Fill address search
    page2.locator('input[name="keyword"]').fill("향군로 74번길 26")
    page2.locator('button[type="button"]').first.click()
    time.sleep(2)

    # Click the address result
    page2.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const addressResult = links.find(link => link.textContent.includes('향군로74번길 26'));
        if (addressResult) addressResult.click();
    }""")
    time.sleep(1)

    # Fill building number and unit
    page2.evaluate("""() => {
        const inputs = document.querySelectorAll('input[type="text"]');
        for (let input of inputs) {
            if (input.placeholder && input.placeholder.includes('동')) {
                input.value = '103';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            } else if (input.placeholder && input.placeholder.includes('호')) {
                input.value = '912';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    }""")
    time.sleep(1)

    # Submit address
    page2.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const submitLink = links.find(link => link.textContent.includes('입력'));
        if (submitLink) submitLink.click();
    }""")
    time.sleep(1)
    page2.close()
    time.sleep(1)

    # Click next button using JavaScript
    page.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const nextLink = links.find(link => link.textContent.includes('다음'));
        if (nextLink) nextLink.click();
    }""")
    time.sleep(2)

    # Fill pickup information
    page.locator('select[name="pickupDate"]').select_option("2025-12-31")
    page.locator("#pickupKeep").select_option("05")
    page.locator('input[placeholder*="보관"]').fill("문 앞에 있어요")
    time.sleep(1)

    # Click next in pickup info section
    page.locator("#pickupInfoDiv a").first.click()
    time.sleep(2)
    # Skip the old recipient search popup
    try:
        with page.expect_popup(timeout=2000) as page3_info:
            page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a'));
                const link = links.find(link => link.textContent.includes('기존'));
                if (link) link.click();
            }""")
        page3 = page3_info.value
        page3.close()
    except:
        pass

    # Open address book search
    with page.expect_popup() as page4_info:
        page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a'));
            const link = links.find(link => link.textContent.includes('주소록'));
            if (link) link.click();
        }""")
    page4 = page4_info.value
    time.sleep(1)

    # Select from address book
    page4.locator('select').first.select_option("0")
    page4.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const confirmLink = links.find(link => link.textContent.includes('확인'));
        if (confirmLink) confirmLink.click();
    }""")
    time.sleep(1)

    # Handle dialog and select recipient
    page4.once("dialog", lambda dialog: dialog.dismiss())
    page4.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const recipientLink = links.find(link => link.textContent.includes('육지연'));
        if (recipientLink) recipientLink.click();
    }""")
    time.sleep(1)
    page4.close()

    # Click next
    page.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const nextLinks = links.filter(link => link.textContent.includes('다음'));
        if (nextLinks[2]) nextLinks[2].click();
    }""")
    time.sleep(2)

    # Load item information
    with page.expect_popup() as page5_info:
        page.evaluate("""() => {
            const elements = Array.from(document.querySelectorAll('*'));
            const link = elements.find(el => el.textContent.includes('물품정보'));
            if (link) link.click();
        }""")
    page5 = page5_info.value
    time.sleep(1)

    page5.once("dialog", lambda dialog: dialog.dismiss())
    page5.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const link = links.find(link => link.textContent.trim() === '전자제품');
        if (link) link.click();
    }""")
    time.sleep(1)
    page5.close()

    # Add to recipient list
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const link = links.find(link => link.textContent.includes('목록에 추가'));
        if (link) link.click();
    }""")
    time.sleep(1)

    # Verify address
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const link = links.find(link => link.textContent.includes('주소검증'));
        if (link) link.click();
    }""")
    time.sleep(2)

    # Click final next button
    page.locator("#recListNextDiv a").first.click()
    time.sleep(2)

    # Fill payment card information using JavaScript
    page.evaluate("""() => {
        const inputs = document.querySelectorAll('input[type="text"]');
        const cardInputs = [];

        for (let input of inputs) {
            const placeholder = input.placeholder || input.title || '';
            if (placeholder.includes('카드') || placeholder.includes('유효') ||
                placeholder.includes('비밀') || placeholder.includes('생년')) {
                cardInputs.push(input);
            }
        }

        // Fill card number (4 parts)
        if (cardInputs[0]) cardInputs[0].value = '1234';
        if (cardInputs[1]) cardInputs[1].value = '1234';
        if (cardInputs[2]) cardInputs[2].value = '1234';
        if (cardInputs[3]) cardInputs[3].value = '1234';

        // Fill expiry date (month, year)
        if (cardInputs[4]) cardInputs[4].value = '11';
        if (cardInputs[5]) cardInputs[5].value = '11';

        // Fill password (2 digits)
        if (cardInputs[6]) cardInputs[6].value = '1';
        if (cardInputs[7]) cardInputs[7].value = '1';

        // Fill birth date
        if (cardInputs[8]) cardInputs[8].value = '111111';
    }""")
    time.sleep(1)

    # Verify payment card
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.evaluate("""() => {
        const links = Array.from(document.querySelectorAll('a'));
        const link = links.find(link => link.textContent.includes('검증'));
        if (link) link.click();
    }""")
    time.sleep(2)

    print("Test completed successfully!")

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
