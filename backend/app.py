from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import csv
import json
import os
import re
import shutil
import subprocess

try:
    import google.generativeai as genai
except ImportError:
    genai = None

load_dotenv()

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

CPP_EVALUATOR_DIR = os.path.join(PROJECT_ROOT, "cpp_evaluator")
REQUEST_BODY_PATH = os.path.join(CPP_EVALUATOR_DIR, "request_body.json")
EXECUTION_METRICS_PATH = os.path.join(CPP_EVALUATOR_DIR, "results", "execution_metrics.csv")
EVALUATOR_EXE_PATH = os.path.join(CPP_EVALUATOR_DIR, "evaluator.exe")

FINALSCORE_DIR = os.path.join(PROJECT_ROOT, "finalscore")
FINALSCORE_CPP_PATH = os.path.join(FINALSCORE_DIR, "finalscore.cpp")
FINALSCORE_EXE_PATH = os.path.join(FINALSCORE_DIR, "finalscore.exe")
FINALSCORE_EXECUTION_INPUT_PATH = os.path.join(FINALSCORE_DIR, "execution_result.csv")
FINALSCORE_SEMANTIC_INPUT_PATH = os.path.join(FINALSCORE_DIR, "semantic_result.csv")
FINALSCORE_RESULT_PATH = os.path.join(FINALSCORE_DIR, "final_scores.csv")

MODEL_COLORS = [
    "oklch(0.78 0.12 250)",
    "oklch(0.8 0.11 35)",
    "oklch(0.78 0.11 160)",
]


@app.route("/api/evaluate", methods=["POST"])
def evaluate_codes():
    try:
        data = request.get_json() or {}
        problem = (data.get("problem") or "").strip()
        language = (data.get("language") or "C++").strip()

        if not problem:
            return jsonify({
                "success": False,
                "message": "problem 데이터가 없습니다."
            }), 400

        submissions = generate_submissions(problem, language)
        request_body = {
            "problem": problem,
            "language": language,
            "submissions": submissions
        }

        save_request_body(request_body)
        build_evaluator_if_needed()
        run_cpp_evaluator()
        save_semantic_result_csv(submissions)
        prepare_finalscore_input_csv()
        build_finalscore_if_needed()
        run_finalscore()

        final_results = parse_finalscore_csv()
        execution_metrics = parse_execution_metrics_csv()
        candidates = build_frontend_candidates_from_finalscore(submissions, final_results, execution_metrics)

        return jsonify({
            "success": True,
            "message": "평가가 완료되었습니다.",
            "candidates": candidates
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": "서버 처리 중 오류가 발생했습니다.",
            "error": str(e)
        }), 500


def clean_code_block(text):
    code = (text or "").strip()
    code = re.sub(r"^```(?:cpp|c\+\+|c|python|java|javascript|typescript)?\s*", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\s*```$", "", code)
    return code.strip()


def generate_code_with_gemini(problem, language):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise Exception("Gemini API 호출 실패: GEMINI_API_KEY가 설정되지 않았습니다.")

    if genai is None:
        raise Exception("Gemini API 호출 실패: google-generativeai 패키지가 설치되지 않았습니다.")

    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    prompt = f"""
Solve the following programming problem in {language}.
Return only source code. Do not include markdown. Do not include explanation.

Problem:
{problem}
""".strip()

    response = model.generate_content(prompt)
    code = clean_code_block(getattr(response, "text", ""))
    if not code:
        raise Exception("Gemini API 호출 실패: 빈 코드 응답을 받았습니다.")

    return {
        "model": "Gemini",
        "code": code
    }


def generate_mock_submission(problem, language, model="Gemini"):
    code = """#include <iostream>
using namespace std;

int main() {
    cout << 0 << endl;
    return 0;
}
"""
    return {
        "model": model,
        "code": code
    }


def generate_code_with_gpt_placeholder(problem, language):
    return generate_mock_submission(problem, language, "GPT")


def generate_code_with_claude_placeholder(problem, language):
    return generate_mock_submission(problem, language, "Claude")


def generate_submissions(problem, language):
    use_mock = os.environ.get("USE_MOCK_LLM", "true").strip().lower() == "true"

    if use_mock:
        return [
            generate_mock_submission(problem, language, "Gemini"),
            generate_code_with_gpt_placeholder(problem, language),
            generate_code_with_claude_placeholder(problem, language),
        ]

    submissions = []

    try:
        submissions.append(generate_code_with_gemini(problem, language))
    except Exception as e:
        if os.environ.get("ALLOW_MOCK_LLM_FALLBACK", "true").strip().lower() == "true":
            print(f"[WARN] {e} Falling back to mock Gemini submission.")
            submissions.append(generate_mock_submission(problem, language, "Gemini"))
        else:
            raise

    submissions.append(generate_code_with_gpt_placeholder(problem, language))
    submissions.append(generate_code_with_claude_placeholder(problem, language))
    return submissions


def save_request_body(data):
    try:
        with open(REQUEST_BODY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise Exception(f"request_body.json 저장 실패: {e}")


def build_evaluator_if_needed():
    evaluator_cpp_path = os.path.join(CPP_EVALUATOR_DIR, "evaluator.cpp")
    evaluator_h_path = os.path.join(CPP_EVALUATOR_DIR, "evaluator.h")
    input_manager_cpp_path = os.path.join(CPP_EVALUATOR_DIR, "InputManager.cpp")
    input_manager_h_path = os.path.join(CPP_EVALUATOR_DIR, "InputManager.h")

    if not os.path.exists(evaluator_cpp_path):
        raise Exception("evaluator.cpp 컴파일 실패: cpp_evaluator/evaluator.cpp 파일을 찾을 수 없습니다.")

    if not os.path.exists(input_manager_cpp_path):
        raise Exception("evaluator.cpp 컴파일 실패: cpp_evaluator/InputManager.cpp 파일을 찾을 수 없습니다.")

    source_paths = [
        p for p in [evaluator_cpp_path, evaluator_h_path, input_manager_cpp_path, input_manager_h_path]
        if os.path.exists(p)
    ]
    should_build = not os.path.exists(EVALUATOR_EXE_PATH)

    if not should_build:
        exe_mtime = os.path.getmtime(EVALUATOR_EXE_PATH)
        should_build = any(os.path.getmtime(path) > exe_mtime for path in source_paths)

    if not should_build:
        return

    result = subprocess.run(
        ["g++", "evaluator.cpp", "InputManager.cpp", "-o", "evaluator.exe", "-std=c++17", "-lpsapi"],
        cwd=CPP_EVALUATOR_DIR,
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace",
        shell=True
    )

    if result.returncode != 0:
        raise Exception(f"evaluator.cpp 컴파일 실패: {result.stderr or result.stdout}")


def run_cpp_evaluator():
    if not os.path.exists(EVALUATOR_EXE_PATH):
        raise Exception("evaluator.exe 실행 실패: evaluator.exe 파일이 없습니다.")

    result = subprocess.run(
        [EVALUATOR_EXE_PATH],
        cwd=CPP_EVALUATOR_DIR,
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace",
        shell=False
    )

    if result.returncode != 0:
        raise Exception(f"evaluator.exe 실행 실패: {result.stderr or result.stdout}")


def save_semantic_result_csv(submissions):
    try:
        with open(FINALSCORE_SEMANTIC_INPUT_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["file_name", "semantic_score"])
            for index, submission in enumerate(submissions):
                # TODO: Replace fixed semantic score with AI-based semantic evaluation.
                writer.writerow([make_candidate_file_name(submission.get("model", ""), index + 1), "0.80"])
    except Exception as e:
        raise Exception(f"semantic_result.csv 생성 실패: {e}")


def prepare_finalscore_input_csv():
    if not os.path.exists(EXECUTION_METRICS_PATH):
        raise Exception("execution_metrics.csv 파일을 찾을 수 없습니다.")

    try:
        shutil.copyfile(EXECUTION_METRICS_PATH, FINALSCORE_EXECUTION_INPUT_PATH)
    except Exception as e:
        raise Exception(f"finalscore 입력 CSV 준비 실패: {e}")


def build_finalscore_if_needed():
    if not os.path.exists(FINALSCORE_CPP_PATH):
        raise Exception("finalscore.cpp 컴파일 실패: finalscore/finalscore.cpp 파일을 찾을 수 없습니다.")

    should_build = not os.path.exists(FINALSCORE_EXE_PATH)

    if not should_build:
        exe_mtime = os.path.getmtime(FINALSCORE_EXE_PATH)
        should_build = os.path.getmtime(FINALSCORE_CPP_PATH) > exe_mtime

    if not should_build:
        return

    result = subprocess.run(
        ["g++", "finalscore.cpp", "-o", "finalscore.exe", "-std=c++17"],
        cwd=FINALSCORE_DIR,
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace",
        shell=True
    )

    if result.returncode != 0:
        raise Exception(f"finalscore.cpp 컴파일 실패: {result.stderr or result.stdout}")


def run_finalscore():
    if not os.path.exists(FINALSCORE_EXE_PATH):
        raise Exception("finalscore.exe 실행 실패: finalscore.exe 파일이 없습니다.")

    result = subprocess.run(
        [FINALSCORE_EXE_PATH],
        cwd=FINALSCORE_DIR,
        capture_output=True,
        text=True,
        encoding="cp949",
        errors="replace",
        shell=False
    )

    if result.returncode != 0:
        raise Exception(f"finalscore.exe 실행 실패: {result.stderr or result.stdout}")


def parse_finalscore_csv():
    if not os.path.exists(FINALSCORE_RESULT_PATH):
        raise Exception("final_scores.csv 파일을 찾을 수 없습니다.")

    results = []
    with open(FINALSCORE_RESULT_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append({
                "rank": int(parse_number(row.get("rank"), 0)),
                "fileName": row.get("file_name", ""),
                "semanticScore": parse_number(row.get("semantic_score")),
                "passRate": parse_number(row.get("pass_rate")),
                "timeScore": parse_number(row.get("time_score")),
                "memoryScore": parse_number(row.get("memory_score")),
                "finalScore": parse_number(row.get("final_score")),
            })

    return results


def parse_execution_metrics_csv():
    if not os.path.exists(EXECUTION_METRICS_PATH):
        raise Exception("execution_metrics.csv 파일을 찾을 수 없습니다.")

    metrics = {}
    with open(EXECUTION_METRICS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_name = row.get("file_name", "")
            if file_name:
                metrics[file_name] = {
                    "runtimeMs": parse_number(row.get("runtime_ms")),
                    "memoryKb": parse_number(row.get("memory_kb")),
                }

    return metrics


def build_frontend_candidates_from_finalscore(submissions, final_results, execution_metrics):
    result_by_file_name = {
        result.get("fileName"): result
        for result in final_results
        if result.get("fileName")
    }

    candidates = []
    for index, submission in enumerate(submissions):
        model = submission.get("model") or f"model_{index + 1}"
        file_name = make_candidate_file_name(model, index + 1)
        result = result_by_file_name.get(file_name, {})
        metrics = execution_metrics.get(file_name, {})

        candidates.append({
            "id": str(index),
            "model": model,
            "color": MODEL_COLORS[index % len(MODEL_COLORS)],
            "code": submission.get("code", ""),
            "scores": {
                "correctness": normalize_score(result.get("passRate")),
                "style": normalize_score(result.get("semanticScore")),
                "performance": normalize_score(result.get("timeScore")),
                "crossReview": normalize_score(result.get("memoryScore")),
            },
            "total": normalize_score(result.get("finalScore")),
            "rank": result.get("rank", index + 1),
            "runtimeMs": metrics.get("runtimeMs", 0),
            "memoryKb": metrics.get("memoryKb", 0),
        })

    candidates.sort(key=lambda candidate: candidate.get("rank", 9999))
    return candidates


def sanitize_model_name(model):
    if not model or not model.strip():
        return ""

    return re.sub(r'[\s/\\:*?"<>|]', "_", model)


def make_candidate_file_name(model, index):
    safe_model_name = sanitize_model_name(model)
    if not safe_model_name:
        safe_model_name = f"model_{index}"

    return f"code_{safe_model_name}.cpp"


def normalize_score(value):
    parsed = parse_number(value)
    if 0.0 <= parsed <= 1.0:
        parsed *= 100
    return round(parsed, 1)


def parse_number(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    app.run(debug=True, port=5000)
