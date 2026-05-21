from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CPP_EVALUATOR_DIR = os.path.join(PROJECT_ROOT, "cpp_evaluator")
AI_MODEL_PATH = os.path.join(PROJECT_ROOT, "ai_model", "ai_model")
REQUEST_BODY_PATH = os.path.join(CPP_EVALUATOR_DIR, "request_body.json")
RESULT_CSV_PATH = os.path.join(CPP_EVALUATOR_DIR, "results", "execution_metrics.csv")
EVALUATOR_EXE_PATH = os.path.join(CPP_EVALUATOR_DIR, "evaluator.exe")
MODEL_COLORS = [
    "oklch(0.78 0.12 250)",
    "oklch(0.8 0.11 35)",
    "oklch(0.78 0.11 160)",
]


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
        semantic_scores = run_ai_semantic_evaluator(data.get("problem", ""), submissions)
        build_evaluator_if_needed()
        run_cpp_evaluator()
        results = parse_csv_result()
        candidates = build_frontend_candidates(submissions, results, semantic_scores)

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


def save_request_body(data):
    with open(REQUEST_BODY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_evaluator_if_needed():
    evaluator_cpp_path = os.path.join(CPP_EVALUATOR_DIR, "evaluator.cpp")
    evaluator_h_path = os.path.join(CPP_EVALUATOR_DIR, "evaluator.h")
    input_manager_cpp_path = os.path.join(CPP_EVALUATOR_DIR, "InputManager.cpp")

    if not os.path.exists(evaluator_cpp_path):
        raise Exception("cpp_evaluator/evaluator.cpp 파일을 찾을 수 없습니다.")

    if not os.path.exists(input_manager_cpp_path):
        raise Exception("cpp_evaluator/InputManager.cpp 파일을 찾을 수 없습니다.")

    source_paths = [evaluator_cpp_path, evaluator_h_path, input_manager_cpp_path]
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
                "semanticScore": parse_number(row.get("semantic_score")),
                "passRate": parse_number(row.get("pass_rate")),
                "timeScore": parse_number(row.get("time_score")),
                "memoryScore": parse_number(row.get("memory_score")),
                "runtimeMs": parse_number(
                    row.get("runtime_ms")
                    or row.get("execution_time_ms")
                    or row.get("runtimeMs")
                ),
                "memoryKb": parse_number(
                    row.get("memory_kb")
                    or row.get("peak_memory_kb")
                    or row.get("memoryKb")
                )
            })

    return results


def run_ai_semantic_evaluator(problem, submissions):
    provider = os.environ.get("AI_SEMANTIC_PROVIDER", "").strip().lower()

    if provider:
        try:
            evaluator = load_ai_model_evaluator()
            score_func = getattr(evaluator, f"get_{provider}_score")
            return [
                normalize_score(score_func(problem, submission.get("code", "")))
                for submission in submissions
            ]
        except Exception as e:
            print(f"[WARN] ai_model semantic evaluation failed: {e}")

    return [
        calculate_local_semantic_score(problem, submission.get("code", ""))
        for submission in submissions
    ]


def load_ai_model_evaluator():
    loader = importlib.machinery.SourceFileLoader("ai_model_module", AI_MODEL_PATH)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module.Performance_measurement()


def calculate_local_semantic_score(problem, code):
    problem_tokens = tokenize(problem)
    code_tokens = tokenize(code)

    if not problem_tokens or not code_tokens:
        return 0.0

    overlap = len(problem_tokens & code_tokens)
    union = len(problem_tokens | code_tokens)

    return round((overlap / union) * 100, 1)


def tokenize(text):
    return set(re.findall(r"\w+", text.lower(), flags=re.UNICODE))


def build_frontend_candidates(submissions, results, semantic_scores=None):
    result_by_file_name = {
        result.get("fileName"): result
        for result in results
        if result.get("fileName")
    }

    candidates = []

    for index, submission in enumerate(submissions):
        model = submission.get("model") or f"model_{index + 1}"
        code = submission.get("code") or ""
        file_name = make_candidate_file_name(model, index + 1)
        result = result_by_file_name.get(file_name)

        if result is None and index < len(results):
            result = results[index]

        result = result or {}

        if semantic_scores and index < len(semantic_scores):
            semantic_score = normalize_score(semantic_scores[index])
        else:
            semantic_score = get_score(result, "semanticScore", "semantic_score")
        pass_rate = get_score(result, "passRate", "pass_rate")
        time_score = get_score(result, "timeScore", "time_score")
        memory_score = get_score(result, "memoryScore", "memory_score")

        total = round(
            semantic_score * 0.3
            + pass_rate * 0.4
            + time_score * 0.2
            + memory_score * 0.1,
            1
        )

        candidates.append({
            "id": str(index),
            "model": model,
            "color": MODEL_COLORS[index % len(MODEL_COLORS)],
            "code": code,
            "scores": {
                "correctness": pass_rate,
                "style": semantic_score,
                "performance": time_score,
                "crossReview": memory_score
            },
            "total": total,
            "runtimeMs": result.get("runtimeMs", 0),
            "memoryKb": result.get("memoryKb", 0)
        })

    return candidates


def make_candidate_file_name(model, fallback_index):
    safe_model_name = make_safe_file_name(model)

    if not safe_model_name:
        safe_model_name = f"model_{fallback_index}"

    return f"code_{safe_model_name}.cpp"


def make_safe_file_name(value):
    if not value or not value.strip():
        return ""

    return re.sub(r'[\s/\\:*?"<>|]', "_", value)


def get_score(result, camel_key, snake_key):
    return normalize_score(parse_number(result.get(camel_key, result.get(snake_key))))


def normalize_score(value):
    value = parse_number(value)

    if 0.0 <= value <= 1.0:
        return round(value * 100, 1)

    return round(value, 1)


def parse_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    app.run(debug=True, port=5000)
