# 보내는 분 주소찾기 진입경로 오류 수정

**Date:** 2025-12-30  
**Scope:** `tests/post_test.py`, `config.yaml`  

## 증상

- "01 보내는 분" 단계에서 **주소찾기**를 눌러야 하는데, 자동화가 자꾸 **"03 받는 분" 주소찾기**로 진입함
- 그 영향으로 "03 받는 분"에서 주소록 수취인 **"육지연"** 선택 플로우가 꼬이거나 진행이 막힘

## 원인

`tests/post_test.py`의 주소찾기 팝업 오픈 로직이 `onclick` 포함 문자열로 링크를 찾도록 되어 있는데,
`config.yaml`에서 트리거가 `"newRePostNum"`(= receiver/03 받는 분)로 고정되어 있었음.

Playwright MCP로 실제 페이지의 "주소찾기" 링크를 확인한 결과, 동일 텍스트("주소찾기")를 가진 링크가 여러 개 존재함:

- **01 보내는 분:** `...('newPostNum', ...)`
- **03 받는 분:** `...('newRePostNum', ...)`
- (기타 sender 관련 링크도 1개 더 존재)

즉, sender 단계에서도 설정값 때문에 receiver 링크를 클릭하고 있었음.

## 해결

1) `config.yaml`에 target별 트리거 분리

- `epost.working_process.address_popup.trigger_onclick_contains_by_target`
  - `sender: "newPostNum"`
  - `recipient: "newRePostNum"`

2) `tests/post_test.py`에서 주소찾기 팝업 오픈 시 target을 명시하고, **보이는 링크만 클릭**하도록 변경

- `toggle_address_popup_trigger(..., target="sender"|"recipient")`
- `open_address_popup(..., target=...)`에서 해당 섹션을 먼저 펼친 뒤 팝업을 열도록 처리

## 검증

- Playwright MCP로 sender/recipient 트리거(`newPostNum`/`newRePostNum`) 존재 확인 및 sender 트리거가 **visible**임을 확인
- 실행: `conda run -n playwright python tests/post_test.py` → **Test completed successfully!**

