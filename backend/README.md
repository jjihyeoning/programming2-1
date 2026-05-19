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
