app.py는 사용자가 보낸 C++ 코드들을 받아서 파일로 저장하고, C++ 평가 프로그램을 실행한 다음, 평가 결과를 다시 화면에 보내주는 중간 연결 담당 코드

Flask = 프론트 요청 받는 서버
request.get_json() = 프론트가 보낸 코드 읽기
save_candidate_codes() = 받은 코드를 .cpp 파일로 저장
subprocess.run() = C++ 평가 프로그램 실행
csv.DictReader() = C++ 평가 결과 읽기
jsonify() = 결과를 프론트로 반환