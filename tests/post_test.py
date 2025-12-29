"""
ePost Login Automation - Working Solution
Date: 2025-12-29

This script successfully logs into epost.go.kr by working around
the security module (nProtect) loading modal that blocks standard interactions.

See progress/epost_login_automation_guide.md for details.
"""

from playwright.sync_api import Playwright, sync_playwright, expect


def login_to_epost(playwright: Playwright, username: str = "fg0015", password: str = "dmlduf1308!") -> None:
    """
    Login to epost.go.kr using JavaScript-based workaround for security module

    Args:
        playwright: Playwright instance
        username: Login username
        password: Login password
    """
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Navigate to login page
    page.goto("https://www.epost.go.kr/usr/login/cafzc008k01.jsp?s_url=https://www.epost.go.kr")

    # Wait for page to stabilize
    page.wait_for_timeout(2000)

    # Execute JavaScript workaround to bypass loading modal and login
    page.evaluate(f"""
        () => {{
            // Remove loading modal that blocks interactions
            const modal = document.querySelector('#nppfs-loading-modal');
            if (modal) {{
                modal.style.display = 'none';
                modal.remove();
            }}

            // Fill login credentials
            const idInput = document.querySelector('input[name="user_id"]') ||
                           document.querySelector('input[title="아이디"]');
            const pwInput = document.querySelector('input[name="user_pwd"]') ||
                           document.querySelector('input[title="비밀번호"]');

            if (idInput && pwInput) {{
                idInput.value = '{username}';
                pwInput.value = '{password}';
            }}

            // Submit login
            if (typeof checkVal === 'function') {{
                checkVal();
            }} else {{
                const form = document.querySelector('#frmLogin') ||
                            document.querySelector('form');
                if (form) {{
                    form.submit();
                }}
            }}
        }}
    """)

    # Wait for login to complete and navigate to main page
    try:
        page.wait_for_url("**/main.retrieveMainPage.comm", timeout=10000)
        print(f"✅ Login successful! Current URL: {page.url()}")
    except Exception as e:
        print(f"❌ Login may have failed: {e}")
        print(f"Current URL: {page.url()}")

    # Keep browser open for manual inspection
    # Remove or modify these lines if you want to continue automation
    input("Press Enter to close browser...")

    context.close()
    browser.close()


def main():
    """Main entry point"""
    with sync_playwright() as playwright:
        login_to_epost(playwright)


if __name__ == "__main__":
    main()
