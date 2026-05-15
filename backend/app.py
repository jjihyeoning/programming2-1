# backend/app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import shutil
import subprocess
import csv

app = Flask(__name__)
CORS(app)

# 현재 app.py 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 프로젝트 루트 경로
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# cpp_evaluator 경로
CPP_EVALUATOR_DIR = os.path.join(PROJECT_ROOT, "cpp_evaluator")

# 후보 코드 저장할 폴더 경로
CANDIDATES_DIR = os.path.join(CPP_EVALUATOR_DIR, "candidates")

# 결과 CSV 경로 => C++ evluator 실행되면 이 파일을 만들고 python이 읽어서 JSON으로 반환
RESULT_CSV_PATH = os.path.join(CPP_EVALUATOR_DIR, "results", "execution_metrics.csv")

# evaluator 실행 파일 경로
EVALUATOR_EXE_PATH = os.path.join(CPP_EVALUATOR_DIR, "evaluator.exe")


#주소 만듦 (POST요청)
@app.route("/api/evaluate", methods=["POST"])
def evaluate_codes(): #프론트에서 코드 보내면 이 함수 실행
    try: #문제 없을 시
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "요청 데이터가 없습니다."
            }), 400

        submissions = data.get("submissions")

        if not submissions:
            return jsonify({
                "success": False,
                "message": "submissions 데이터가 없습니다."
            }), 400

        # 1. candidates 폴더 초기화
        reset_candidates_folder()

        # 2. 프론트에서 받은 코드들을 .cpp 파일로 저장
        saved_files = save_candidate_codes(submissions)

        # 3. evaluator.exe가 없으면 먼저 컴파일
        build_evaluator_if_needed()

        # 4. C++ evaluator 실행
        run_cpp_evaluator()

        # 5. CSV 결과 읽기
        results = parse_csv_result()

        return jsonify({
            "success": True,
            "message": "평가가 완료되었습니다.",
            "savedFiles": saved_files,
            "results": results
        })

    except Exception as e: #문제 있을 시
        return jsonify({
            "success": False,
            "message": "서버 처리 중 오류가 발생했습니다.",
            "error": str(e)
        }), 500


def reset_candidates_folder(): #기존의 candidate 폴더 내 후보 코드 삭제
    
    if os.path.exists(CANDIDATES_DIR):
        shutil.rmtree(CANDIDATES_DIR)

    os.makedirs(CANDIDATES_DIR, exist_ok=True)


def save_candidate_codes(submissions): #프론트에서 받은 후보 코드들을 .cpp 파일로 저장
    
    saved_files = []

    for index, item in enumerate(submissions):
        #후보 코드들 꺼내기
        model_name = item.get("model", f"model_{index + 1}")
        code = item.get("code", "")

        if not code.strip():
            continue

        safe_model_name = make_safe_filename(model_name)
        file_name = f"code_{safe_model_name}.cpp"
        file_path = os.path.join(CANDIDATES_DIR, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        saved_files.append(file_name)

    if not saved_files:
        raise Exception("저장된 코드 파일이 없습니다. code 값이 비어있는지 확인하세요.")

    return saved_files


def make_safe_filename(name):# 파일 이름에 쓰기 위험한 문자를 제거
    
    return (
        name.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )


def build_evaluator_if_needed(): #evaluator.exe가 없으면 evaluator.cpp를 컴파일
   
    if os.path.exists(EVALUATOR_EXE_PATH):
        return

    evaluator_cpp_path = os.path.join(CPP_EVALUATOR_DIR, "evaluator.cpp")

    if not os.path.exists(evaluator_cpp_path):
        raise Exception("cpp_evaluator/evaluator.cpp 파일을 찾을 수 없습니다.")

    compile_command = [
        "g++",
        "evaluator.cpp",
        "-o",
        "evaluator.exe",
        "-std=c++17",
        "-lpsapi"
    ]

    result = subprocess.run(
        compile_command,
        cwd=CPP_EVALUATOR_DIR,
        capture_output=True,
        text=True,
        shell=True
    )

    if result.returncode != 0:
        raise Exception(f"evaluator.cpp 컴파일 실패: {result.stderr}")


def run_cpp_evaluator(): #C++ evaluator.exe를 실행
   
    if not os.path.exists(EVALUATOR_EXE_PATH):
        raise Exception("evaluator.exe 파일이 없습니다.")

    result = subprocess.run(
        ["evaluator.exe"],
        cwd=CPP_EVALUATOR_DIR,
        capture_output=True,
        text=True,
        shell=True
    )

    if result.returncode != 0:
        raise Exception(f"C++ evaluator 실행 실패: {result.stderr}")


def parse_csv_result(): #C++ evaluator가 생성한 execution_metrics.csv를 읽어서 JSON 형태로 변환
  
    
    if not os.path.exists(RESULT_CSV_PATH):
        raise Exception("결과 CSV 파일을 찾을 수 없습니다.")

    results = []

    with open(RESULT_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            results.append({
                "fileName": row.get("file_name"),
                "semanticScore": float(row.get("semantic_score", 0)),
                "passRate": float(row.get("pass_rate", 0)),
                "timeScore": float(row.get("time_score", 0)),
                "memoryScore": float(row.get("memory_score", 0))
            })

    return results


if __name__ == "__main__":
    app.run(debug=True, port=5000)