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
1. 진입경로 수정 
2. 순서 일치하기 
3. 그건 상관 없어. V2는 채워넣는 용이라서 잘 되어 있다 생각한건 굳이 녹화 안했어 
4. 수령인 처리 수기가 아니라 이제 메뉴로 들어갈텐데? 
5. "다음"은 항상 해당 메뉴가 끝나면 시행하는거다. 
6. 그거 해야지. 