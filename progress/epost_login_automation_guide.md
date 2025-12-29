# ePost Login Automation Guide

## Quick Reference

### Working Playwright Code

```python
from playwright.sync_api import sync_playwright

def login_to_epost(username: str, password: str):
    """
    Login to epost.go.kr using JavaScript-based workaround
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Navigate to login page
        page.goto('https://www.epost.go.kr/usr/login/cafzc008k01.jsp?s_url=https://www.epost.go.kr')

        # Wait for page to stabilize
        page.wait_for_timeout(2000)

        # Execute JavaScript to bypass loading modal and login
        page.evaluate(f"""
            () => {{
                // Remove loading modal
                const modal = document.querySelector('#nppfs-loading-modal');
                if (modal) {{
                    modal.style.display = 'none';
                    modal.remove();
                }}

                // Fill credentials
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

        # Wait for navigation
        page.wait_for_url('**/main.retrieveMainPage.comm', timeout=10000)

        print(f"Login successful! Current URL: {page.url}")

        # Handle any popups if needed
        # page.get_by_role('button', name='Close').click() # Example

        return page, browser

# Usage
page, browser = login_to_epost('fg0015', 'dmlduf1308!')
```

## Playwright MCP Commands

### Using Playwright MCP

```javascript
// 1. Navigate
await page.goto('https://www.epost.go.kr/usr/login/cafzc008k01.jsp?s_url=https://www.epost.go.kr');

// 2. Wait
await new Promise(f => setTimeout(f, 2000));

// 3. Execute workaround
await page.evaluate(() => {
    // Remove modal
    const modal = document.querySelector('#nppfs-loading-modal');
    if (modal) {
        modal.style.display = 'none';
        modal.remove();
    }

    // Fill and submit
    const idInput = document.querySelector('input[name="user_id"]');
    const pwInput = document.querySelector('input[name="user_pwd"]');

    if (idInput && pwInput) {
        idInput.value = 'fg0015';
        pwInput.value = 'dmlduf1308!';
    }

    if (typeof checkVal === 'function') {
        checkVal();
    }
});
```

## Alternative Approaches (If JavaScript Method Fails)

### Method 2: Force Click with Playwright

```python
# Remove modal first
page.evaluate("document.querySelector('#nppfs-loading-modal')?.remove()")

# Then fill and click normally
page.fill('input[name="user_id"]', username)
page.fill('input[name="user_pwd"]', password)
page.click('a[onclick="checkVal();"]', force=True)
```

### Method 3: Wait for Network Idle

```python
# Sometimes waiting for network helps
page.goto(url, wait_until='networkidle')
page.wait_for_timeout(3000)

# Then proceed with normal interaction
```

## Troubleshooting

### Issue: Loading modal persists
**Solution:** Use `page.evaluate()` to forcefully remove it

### Issue: Form not submitting
**Solution:** Try both `checkVal()` function and `form.submit()`

### Issue: Credentials not recognized
**Solution:** Check input selectors - use both `name` and `title` attributes

### Issue: Page redirects unexpectedly
**Solution:** Add `page.wait_for_url()` with pattern matching

## Element Selectors Reference

| Element | Selector Options |
|---------|-----------------|
| ID Input | `input[name="user_id"]`<br/>`input[title="아이디"]` |
| Password Input | `input[name="user_pwd"]`<br/>`input[title="비밀번호"]` |
| Login Form | `#frmLogin` |
| Login Button | `a[onclick="checkVal();"]`<br/>`#frmLogin a[title="로그인"]` |
| Loading Modal | `#nppfs-loading-modal` |

## Expected Behavior

1. Login page loads with security modules
2. Loading modal appears (`#nppfs-loading-modal`)
3. JavaScript removes modal and fills form
4. Page redirects to main page
5. Popup may appear (우체국페이 알림)

## Success Indicators

- URL changes to: `https://www.epost.go.kr/main.retrieveMainPage.comm`
- Page title: `인터넷우체국`
- User menu appears in top right

## Notes

- This workaround is necessary due to nProtect or similar security software
- Standard Playwright clicks will timeout due to modal overlay
- The `checkVal()` function performs form validation before submission
- Always test with headless=False first to see visual feedback
