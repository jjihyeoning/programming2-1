from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import json
import os
import subprocess

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CPP_EVALUATOR_DIR = os.path.join(PROJECT_ROOT, "cpp_evaluator")
REQUEST_BODY_PATH = os.path.join(CPP_EVALUATOR_DIR, "request_body.json")
RESULT_CSV_PATH = os.path.join(CPP_EVALUATOR_DIR, "results", "execution_metrics.csv")
EVALUATOR_EXE_PATH = os.path.join(CPP_EVALUATOR_DIR, "evaluator.exe")


@app.route("/api/evaluate", methods=["POST"])
def evaluate_codes():
    try:
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

        save_request_body(data)
        build_evaluator_if_needed()
        run_cpp_evaluator()
        results = parse_csv_result()

        return jsonify({
            "success": True,
            "message": "평가가 완료되었습니다.",
            "results": results
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": "서버 처리 중 오류가 발생했습니다.",
            "error": str(e)
        }), 500


def save_request_body(data):
    with open(REQUEST_BODY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_evaluator_if_needed():
    evaluator_cpp_path = os.path.join(CPP_EVALUATOR_DIR, "evaluator.cpp")
    input_manager_cpp_path = os.path.join(CPP_EVALUATOR_DIR, "InputManager.cpp")

    if not os.path.exists(evaluator_cpp_path):
        raise Exception("cpp_evaluator/evaluator.cpp 파일을 찾을 수 없습니다.")

    if not os.path.exists(input_manager_cpp_path):
        raise Exception("cpp_evaluator/InputManager.cpp 파일을 찾을 수 없습니다.")

    source_paths = [evaluator_cpp_path, input_manager_cpp_path]
    should_build = not os.path.exists(EVALUATOR_EXE_PATH)

    if not should_build:
        exe_mtime = os.path.getmtime(EVALUATOR_EXE_PATH)
        should_build = any(os.path.getmtime(path) > exe_mtime for path in source_paths)

    if not should_build:
        return

    compile_command = [
        "g++",
        "evaluator.cpp",
        "InputManager.cpp",
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
        encoding="utf-8",
        errors="replace",
        shell=True
    )

    if result.returncode != 0:
        raise Exception(f"evaluator 컴파일 실패: {result.stderr}")


def run_cpp_evaluator():
    if not os.path.exists(EVALUATOR_EXE_PATH):
        raise Exception("evaluator.exe 파일이 없습니다.")

    result = subprocess.run(
        ["evaluator.exe"],
        cwd=CPP_EVALUATOR_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True
    )

    if result.returncode != 0:
        raise Exception(f"C++ evaluator 실행 실패: {result.stderr}")


def parse_csv_result():
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
