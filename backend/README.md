# Backend

## 역할

이 폴더는 프론트엔드와 C++ 평가 엔진을 연결하는 Flask 기반 백엔드 서버를 담당한다.

백엔드는 코드 평가를 직접 수행하지 않고, 프론트엔드에서 받은 요청 데이터를 `cpp_evaluator/request_body.json`으로 저장한 뒤 C++ evaluator를 실행한다. 이후 C++ 평가 결과 CSV를 읽어 JSON 형태로 프론트엔드에 반환한다.

## 현재 동작 흐름

```txt
프론트엔드
→ POST /api/evaluate
→ backend/app.py
→ cpp_evaluator/request_body.json 저장
→ C++ evaluator 실행
→ InputManager가 후보 코드 .cpp 파일 생성
→ evaluator가 컴파일/실행/성능 측정
→ execution_metrics.csv 생성
→ 백엔드가 JSON으로 반환
```

````md
## InputManager 연동 설명

이번 수정에서는 기존에 Python 백엔드가 담당하던 후보 코드 파일 생성 기능을 C++ 평가 엔진 내부로 옮겼다.

기존 구조에서는 `backend/app.py`가 프론트엔드에서 전달받은 `submissions` 데이터를 직접 읽고, 각 후보 코드를 `cpp_evaluator/candidates` 폴더에 `.cpp` 파일로 저장했다.

수정 후에는 백엔드가 후보 코드를 직접 저장하지 않고, 요청 JSON 전체를 `cpp_evaluator/request_body.json` 파일로 저장한다. 이후 백엔드가 C++ evaluator를 실행하면, evaluator 내부에서 `InputManager`가 먼저 실행되어 `request_body.json`을 읽고 후보 코드 파일을 생성한다.

`InputManager`는 `cpp_evaluator/InputManager.h`와 `cpp_evaluator/InputManager.cpp`로 구성된다.

`InputManager.h`는 `evaluator.cpp`에서 사용할 함수 선언을 제공한다.

```cpp
void prepareCandidatesFromRequestJson();
````

`InputManager.cpp`는 실제 후보 코드 생성 로직을 담당한다. 주요 역할은 다음과 같다.

```txt
request_body.json 파일 읽기
submissions 배열에서 model, code 값 추출
candidates 폴더 초기화
모델명을 기반으로 code_모델명.cpp 파일 생성
code 문자열의 escape 문자 복원
파일명에 사용할 수 없는 문자 처리
빈 model 값에 대한 기본 이름 부여
빈 code 값은 저장하지 않고 skip
```

예를 들어 프론트엔드에서 다음과 같은 요청이 전달되면,

```json
{
  "submissions": [
    {
      "model": "gpt",
      "code": "#include <iostream>\nusing namespace std;\nint main(){ cout << 1; return 0; }"
    },
    {
      "model": "gemini",
      "code": "#include <iostream>\nusing namespace std;\nint main(){ cout << 2; return 0; }"
    }
  ]
}
```

백엔드는 이 내용을 `cpp_evaluator/request_body.json`으로 저장한다. 이후 C++ evaluator가 실행되면 `InputManager`가 해당 JSON을 읽어 아래와 같은 후보 코드 파일을 생성한다.

```txt
cpp_evaluator/candidates/code_gpt.cpp
cpp_evaluator/candidates/code_gemini.cpp
```

## Run

Backend:

```bash
cd backend
python app.py
```

Frontend:

```bash
cd frontend
npm run dev
```

`POST /api/evaluate` now returns frontend-ready `candidates`. The backend maps
CSV evaluator scores into `scores`, calculates `total`, and keeps the frontend
thin by letting it render the returned candidates directly.

## Current End-to-End Pipeline

```txt
frontend
-> POST /api/evaluate with { problem, language }
-> backend/app.py generates submissions through Gemini or mock fallback
-> cpp_evaluator/request_body.json
-> cpp_evaluator/evaluator.exe
-> cpp_evaluator/results/execution_metrics.csv
-> finalscore/semantic_result.csv
-> finalscore/execution_result.csv
-> finalscore/finalscore.exe
-> finalscore/final_scores.csv
-> backend/app.py returns frontend-ready candidates JSON
```

Frontend request body:

```json
{
  "problem": "problem text",
  "language": "C++"
}
```

Backend `.env` values:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
USE_MOCK_LLM=true
ALLOW_MOCK_LLM_FALLBACK=true
```

For local development without API keys, copy `backend/.env.example` to
`backend/.env` and keep `USE_MOCK_LLM=true`.

For Gemini code generation, set `USE_MOCK_LLM=false` and provide
`GEMINI_API_KEY`. GPT and Claude generation are separated as placeholders in
`backend/app.py` so they can be replaced with real API calls later.

