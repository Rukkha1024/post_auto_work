conda run -n playwright npx playwright codegen --target=python --output tests/post_test_V2.py https://www.epost.go.kr/usr/login/cafzc008k01.jsp?s_url=https://www.epost.go.kr

fg0015
dmlduf1308!

=========
run post_test.py and check the progress well. 

User interest in web automation. 
Read 'progress/' folder's file and use playwright mcp before run the script. 
if it does not working, capture the screenshot and fix the problem. 

command: `conda run -n playwright python tests/post_test.py`

======
implement @plan.md 

===========
post_test_V2.py의 작업 내용과 순서가 post_test.py과 일치하는지  확인해봐. 없는 것 같은데?
<exclude> 내용은 녹화하지 않았다. 
<exclude>
- login
- card info
</exclue>

======
<purpose>
@post_test.py 수정 필요
</purpose>
<rule>
Read 'progress/' folder's file and use playwright mcp before run the script.
너는 지금 progress 하나 실행하고 제대로 되는지 확인을 해야 한다. playwright mcp를 사용해서 작업을 해라.    
</rule>
<problem>
04 물품정보에서 다음의 progress가 안됨. 

1. 03에서 "다음"
2. "물품정보 불러오기"
3. 전자제품 클릭 
4. 크롬 팝업 "확인" 클릭 
5. 배송시 특이사항 작성 
6. "받는 분 목록에 추가" 클릭 
</problem>

------===========
- [ ] 주소검증에서 원래 육지연 2개 나오나? 

==========
'b424a27b1c8c02e2391ec9df8eb97fe9e3fe56f8' 방금 한게 SKILLS 사용해서 한 것 같아. 이거 괜찮네. 아예 이렇게 리팩토링 해줄 수 있나? 
config.yaml의 "working_process" 에 한해서 리팩토링해라. 
그리고 기존 결과물과 동일한지 철저하게 검증해야 한다. 