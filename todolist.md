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

===========
<main issue>
`python tests\post_test.py` 실행 시, 택배 주소 파싱에 대한 수정요청이다. 
난 이게 결국 자동화로 만들건데, 지금 택배주소를 ai가 파싱할 수는 없어. 파이썬으로 어떤 룰이 있어야해. 

택배주소 파싱에 있어서 지금 로직이 맞는지 모르겠어. 
</main issue>

<progress>
1. web search로 택배주소 파싱을 어떻게 하는게 맞을지 생각. 
2. `질병청구글시트복제본.xlsx`의 `택배 회수장소 주소` column 내 value에 대해서 직접 주소 파싱을 해서 제대로 반영되는지 확인. 
3, 굳이 우체국에서 안하고 다른 python api, library 등을 통해 주소랑 동호수 파싱해서 나온거랑 맞는지 확인. 
</progress>

============
관리번호=144 / 이름=정화정, 관리번호=142 / 이름=변지연
에 대해서 주소파싱이 제대로 안된다. 
엑셀 내 값("서울 관악구 인헌21길 5, 대림빌라 302호 (정화정님과 한 가구)")에서 '서울 관악구 인헌21길 5, 대림빌라 302호'가 실제 주소인데, "대림빌라 302호"가 빠져서 파싱된다. 
이 부분에 대해서 코드를 수정해야 한다.


검색은 "서울 관악구 인헌21길 5"
나머지가 unit. 

내가 볼 때 너 주소 parsing에 대해서 규칙이 정확하지 않은 것 같은데


==========
