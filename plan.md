# post_test.py 수정 계획

## 목적
post_test_V2.py에 recording된 추가 작업 단계를 post_test.py에 통합

## 현재 상황 분석

### post_test.py의 현재 흐름
1. 로그인
2. 택배 예약 페이지 접속
3. 필수 체크박스 동의
4. 방문일/시간/보관방법 선택
5. 무게/부피/품목 선택
6. 수신자 정보 입력 (주소록 또는 수동)
7. **→ 바로 다음 단계로 진행** (tests/post_test.py:529-531)
8. 결제 정보 입력

### post_test_V2.py의 추가 작업 (라인 28-38)
주소록 선택 후, 다음 단계로 진행하기 전에:
1. **물품정보 불러오기** 팝업 처리
   - "물품정보 불러오기" 클릭 → 팝업 열기
   - 다이얼로그 dismiss
   - "전자제품" 링크 클릭
   - 팝업 닫기

2. **받는 분 목록에 추가**
   - 다이얼로그 dismiss
   - "받는 분 목록에 추가" 링크 클릭

3. **주소검증**
   - 다이얼로그 dismiss
   - "주소검증" 링크 클릭

4. 그 후 "다음" 버튼으로 진행

## 수정 계획

### 1. config.yaml에 새로운 설정 추가
**위치**: `epost.working_process` 섹션

```yaml
epost:
  working_process:
    # 기존 항목들...

    # 새로 추가할 항목
    item_info:
      popup_trigger_text: "물품정보 불러오기"
      item_selection_text: "전자제품"  # 선택할 품목명

    recipient_list:
      add_button_text: "받는 분 목록에 추가"

    address_validation:
      button_text: "주소검증"
```

### 2. post_test.py에 헬퍼 함수 추가

#### 2-1. `open_item_info_popup()` 함수
**위치**: 약 라인 375 이후 (address_book 관련 함수들 다음)

**기능**:
- "물품정보 불러오기" 텍스트로 링크 클릭
- 팝업 대기 및 반환
- TimeoutError 처리

**구현 패턴**: `open_address_book_popup()` 함수와 유사

#### 2-2. `select_item_in_popup()` 함수
**위치**: `open_item_info_popup()` 다음

**기능**:
- 팝업에서 품목명 텍스트로 링크 찾기
- 클릭 및 step_delay
- 팝업 닫기

#### 2-3. `add_to_recipient_list()` 함수
**위치**: `select_item_in_popup()` 다음

**기능**:
- "받는 분 목록에 추가" 링크 클릭
- click_link_by_text 재사용

#### 2-4. `validate_address()` 함수
**위치**: `add_to_recipient_list()` 다음

**기능**:
- "주소검증" 링크 클릭
- click_link_by_text 재사용

### 3. run() 함수 수정
**위치**: tests/post_test.py:526-531 (수신자 정보 입력 후)

**기존 코드** (라인 526-531):
```python
        if manual_entry_required:
            fill_manual_recipient(page, config, timeouts)

        click_selector(page, "#imgBtn", timeouts["action"])
        click_selector(page, "#btnAddr", timeouts["action"])
        click_link_by_text(page, "다음", "#recListNextDiv", timeouts["action"])
```

**수정 후**:
```python
        if manual_entry_required:
            fill_manual_recipient(page, config, timeouts)

        # 물품정보 불러오기 팝업 처리
        item_info_cfg = process_cfg["item_info"]
        page_item = open_item_info_popup(page, config, timeouts["action"])
        page_item.once("dialog", lambda dialog: dialog.dismiss())
        select_item_in_popup(page_item, item_info_cfg["item_selection_text"], timeouts["action"])

        # 받는 분 목록에 추가
        page.once("dialog", lambda dialog: dialog.dismiss())
        add_to_recipient_list(page, config, timeouts["action"])

        # 주소검증
        page.once("dialog", lambda dialog: dialog.dismiss())
        validate_address(page, config, timeouts["action"])

        click_selector(page, "#imgBtn", timeouts["action"])
        click_selector(page, "#btnAddr", timeouts["action"])
        click_link_by_text(page, "다음", "#recListNextDiv", timeouts["action"])
```

### 4. 다이얼로그 처리 전략
- `page.once("dialog", ...)`: 일회성 다이얼로그 처리 (V2에서 사용한 패턴)
- 각 작업 전에 dismiss 핸들러 등록

## 구현 순서

1. **config.yaml 수정**: item_info, recipient_list, address_validation 설정 추가
2. **헬퍼 함수 작성**: 4개의 새 함수 추가 (라인 375 이후)
3. **run() 함수 수정**: 라인 526-531 사이에 새 작업 단계 삽입
4. **테스트**: 수정된 코드 실행 및 검증
5. **Git 커밋**: 한국어 커밋 메시지로 커밋

## 예상 리스크 및 대응

### 리스크 1: 팝업 타이밍 이슈
- **대응**: popup_timeout_ms 사용, try-except로 명확한 에러 메시지

### 리스크 2: 다이얼로그 미발생
- **대응**: once() 사용으로 다이얼로그 미발생 시 무시

### 리스크 3: 선택자 변경
- **대응**: config.yaml의 텍스트 기반 선택으로 유연성 확보

## 검증 방법

1. 스크립트 실행 후 각 단계별 스크린샷 확인
2. 로그 출력으로 각 단계 완료 확인
3. 최종 결제 페이지 도달 여부 확인

## 참고사항

- **기존 로직 유지**: 주소록/수동 입력 분기는 그대로 유지
- **재사용성**: 헬퍼 함수로 분리하여 향후 유지보수 용이
- **설정 중심**: 모든 텍스트는 config.yaml에서 관리
