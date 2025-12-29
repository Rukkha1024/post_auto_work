# Plan

- Update config.yaml to include address-book empty-result handling and keep ePost settings aligned with tests/post_test.py.
- Adjust tests/post_test.py to detect an empty address-book list and fall back to manual recipient entry (address popup + phone).
- Commit changes with a Korean message.
- Verify interpreter path and run `conda run -n playwright python tests/post_test.py` in the new session.
