from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import csv
import json
import os
import re
import shutil
import subprocess
import numpy as np

# ── LLM 라이브러리 (없으면 None으로 처리) ────────────────────────────────
try:
    from google import genai as google_genai
except ImportError:
    google_genai = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import anthropic
except ImportError:
    anthropic = None
# ─────────────────────────────────────────────────────────────────────────

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
SEMANTIC_FILTER_DIR = os.path.join(PROJECT_ROOT, "semantic_filter")
PASSED_CANDIDATES_PATH = os.path.join(SEMANTIC_FILTER_DIR, "passed_candidates.csv")


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

        # 1. LLM 후보 코드 3개 생성
        all_submissions = generate_submissions(problem, language)

        # 2. semantic_filter.cpp가 통과시킨 후보만 남김
        passed_submissions = filter_passed_submissions(all_submissions)

        if not passed_submissions:
            return jsonify({
                "success": False,
                "message": "semantic 필터를 통과한 후보 코드가 없습니다."
            }), 400

        print("[FILTER] 전체 후보 수:", len(all_submissions))
        print("[FILTER] 통과 후보 수:", len(passed_submissions))
        print("[FILTER] 통과 모델:", [
            submission["model"] for submission in passed_submissions
        ])

        # 3. 통과 후보만 cpp_evaluator 입력 JSON으로 저장
        request_body = {
            "problem": problem,
            "language": language,
            "submissions": passed_submissions
        }

        save_request_body(request_body)

        # 4. 통과 후보만 C++ 실행 평가
        build_evaluator_if_needed()
        run_cpp_evaluator()
        save_semantic_result_csv(passed_submissions, problem)

        # 5. cpp_evaluator 결과를 finalscore 입력으로 준비
        prepare_finalscore_input_csv()

        # 6. 최종 점수 계산
        build_finalscore_if_needed()
        run_finalscore()

        # 7. 프론트에 보여줄 결과 생성
        final_results = parse_finalscore_csv()
        execution_metrics = parse_execution_metrics_csv()

        candidates = build_frontend_candidates_from_finalscore(
            passed_submissions,
            final_results,
            execution_metrics
        )

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


# ── 공통 유틸 ─────────────────────────────────────────────────────────────

def clean_code_block(text):
    """LLM 응답에서 마크다운 코드 블록 제거"""
    code = (text or "").strip()
    code = re.sub(r"^```(?:cpp|c\+\+|c|python|java|javascript|typescript)?\s*", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\s*```$", "", code)
    return code.strip()


def build_prompt(problem, language):
    """세 모델 공통 프롬프트"""
    return (
        f"Solve the following programming problem in {language}.\n\n"
        "STRICT RULES — follow every rule or the answer is wrong:\n"
        "1. Return ONLY the source code. No markdown fences (```), no explanations, no comments.\n"
        "2. Do NOT use cin, scanf, getline, or any form of standard input (stdin).\n"
        "3. All input values must be hardcoded as constants directly in the code.\n"
        "4. The program must run and print its result immediately with no user interaction.\n"
        "5. Use cout (not printf) for output.\n\n"
        f"Problem:\n{problem}"
    )


# ── Gemini ────────────────────────────────────────────────────────────────

def generate_code_with_gemini(problem, language):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise Exception("GEMINI_API_KEY가 .env에 설정되지 않았습니다.")
    if google_genai is None:
        raise Exception("google-genai 패키지가 설치되지 않았습니다. (pip install google-genai)")

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    client = google_genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=build_prompt(problem, language),
    )
    code = clean_code_block(response.text or "")
    if not code:
        raise Exception("Gemini API가 빈 응답을 반환했습니다.")

    return {"model": "Gemini", "code": code}


# ── GPT (OpenAI) ──────────────────────────────────────────────────────────

def generate_code_with_gpt(problem, language):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise Exception("OPENAI_API_KEY가 .env에 설정되지 않았습니다.")
    if OpenAI is None:
        raise Exception("openai 패키지가 설치되지 않았습니다. (pip install openai)")

    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": build_prompt(problem, language)}],
        temperature=0.2,
    )
    code = clean_code_block(response.choices[0].message.content or "")
    if not code:
        raise Exception("GPT API가 빈 응답을 반환했습니다.")

    return {"model": "GPT", "code": code}


# ── Claude (Anthropic) ────────────────────────────────────────────────────

def generate_code_with_claude(problem, language):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY가 .env에 설정되지 않았습니다.")
    if anthropic is None:
        raise Exception("anthropic 패키지가 설치되지 않았습니다. (pip install anthropic)")

    model_name = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model_name,
        max_tokens=4096,
        messages=[{"role": "user", "content": build_prompt(problem, language)}],
    )
    code = clean_code_block(message.content[0].text or "")
    if not code:
        raise Exception("Claude API가 빈 응답을 반환했습니다.")

    return {"model": "Claude", "code": code}


# ── Mock (테스트용) ───────────────────────────────────────────────────────

def generate_mock_submission(problem, language, model="Gemini"):
    code = "#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << 0 << endl;\n    return 0;\n}\n"
    return {"model": model, "code": code}


# ── 제출 코드 생성 (메인 로직) ────────────────────────────────────────────

def generate_submissions(problem, language):
    """
    USE_MOCK_LLM=true  → 세 모델 모두 목업 코드 반환 (API 키 불필요)
    USE_MOCK_LLM=false → 실제 API 호출. 키가 없거나 실패 시
                         ALLOW_MOCK_LLM_FALLBACK=true 이면 목업으로 대체.
    """
    use_mock = os.environ.get("USE_MOCK_LLM", "true").strip().lower() == "true"
    allow_fallback = os.environ.get("ALLOW_MOCK_LLM_FALLBACK", "true").strip().lower() == "true"

    if use_mock:
        print("[INFO] USE_MOCK_LLM=true → 목업 코드를 사용합니다.")
        return [
            generate_mock_submission(problem, language, "Gemini"),
            generate_mock_submission(problem, language, "GPT"),
            generate_mock_submission(problem, language, "Claude"),
        ]

    llm_generators = [
        ("Gemini", generate_code_with_gemini),
        ("GPT",    generate_code_with_gpt),
        ("Claude", generate_code_with_claude),
    ]

    submissions = []
    for model_name, generator in llm_generators:
        try:
            submission = generator(problem, language)
            print(f"[INFO] {model_name} 코드 생성 완료.")
            submissions.append(submission)
        except Exception as e:
            if allow_fallback:
                print(f"[WARN] {model_name} 실패: {e} → 목업으로 대체합니다.")
                submissions.append(generate_mock_submission(problem, language, model_name))
            else:
                raise Exception(f"{model_name} API 호출 실패: {e}")

    return submissions


# ── 이하 기존 코드 유지 ───────────────────────────────────────────────────

def save_request_body(data):
    try:
        with open(REQUEST_BODY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise Exception(f"request_body.json 저장 실패: {e}")

def filter_passed_submissions(submissions):
    """
    semantic_filter/passed_candidates.csv 가 있으면 해당 모델만 통과시키고,
    파일이 없으면 전체 제출을 그대로 반환한다.
    """
    if not os.path.exists(PASSED_CANDIDATES_PATH):
        print("[INFO] passed_candidates.csv 없음 → 전체 후보 통과")
        return submissions

    passed_models = []
    try:
        with open(PASSED_CANDIDATES_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                passed_models.append(row.get("code_model", ""))
    except Exception as e:
        print(f"[WARN] passed_candidates.csv 읽기 실패: {e} → 전체 후보 통과")
        return submissions

    filtered = [s for s in submissions if s.get("model") in passed_models]
    return filtered if filtered else submissions

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


# ── Semantic Score (AI 평가 모델) ────────────────────────────────────────

def _cosine_sim(a, b):
    """두 벡터의 코사인 유사도 (0~1)"""
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _score_openai(problem, code):
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or OpenAI is None:
        return None
    client = OpenAI(api_key=key)
    q = client.embeddings.create(input=[problem], model="text-embedding-3-large").data[0].embedding
    c = client.embeddings.create(input=[code],    model="text-embedding-3-large").data[0].embedding
    return _cosine_sim(q, c)


def _score_voyage(problem, code):
    key = os.environ.get("VOYAGE_API_KEY", "").strip()
    if not key:
        return None
    import voyageai
    vo = voyageai.Client(api_key=key)
    q = vo.embed([problem], model="voyage-code-3", input_type="query").embeddings[0]
    c = vo.embed([code],    model="voyage-code-3", input_type="document").embeddings[0]
    return _cosine_sim(q, c)


def _score_cohere(problem, code):
    key = os.environ.get("COHERE_API_KEY", "").strip()
    if not key:
        return None
    import cohere
    co = cohere.Client(key)
    q = co.embed(texts=[problem], model="embed-multilingual-v3.0", input_type="search_query").embeddings[0]
    c = co.embed(texts=[code],    model="embed-multilingual-v3.0", input_type="search_document").embeddings[0]
    return _cosine_sim(q, c)


def _score_jina(problem, code):
    key = os.environ.get("JINA_API_KEY", "").strip()
    if not key:
        return None
    import requests as req
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    def embed(text, task):
        res = req.post("https://api.jina.ai/v1/embeddings",
                       headers=headers,
                       json={"model": "jina-embeddings-v3", "task": task, "input": [text]})
        return res.json()["data"][0]["embedding"]
    return _cosine_sim(embed(problem, "retrieval.query"), embed(code, "retrieval.passage"))


def _score_nomic(problem, code):
    key = os.environ.get("NOMIC_API_KEY", "").strip()
    if not key:
        return None
    import requests as req
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    def embed(text, task):
        res = req.post("https://api-atlas.nomic.ai/v1/embedding/text",
                       headers=headers,
                       json={"model": "nomic-embed-text-v1.5", "task_type": task, "texts": [text]})
        return res.json()["embeddings"][0]
    return _cosine_sim(embed(problem, "search_query"), embed(code, "search_document"))


def _score_zeroentropy(problem, code):
    key = os.environ.get("ZEROENTROPY_API_KEY", "").strip()
    if not key:
        return None
    import requests as req
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    def embed(text):
        res = req.post("https://api.zeroentropy.ai/v1/embeddings",
                       headers=headers,
                       json={"model": "zembed-1", "input": [text]})
        return res.json()["data"][0]["embedding"]
    return _cosine_sim(embed(problem), embed(code))


def calculate_semantic_score(problem, code):
    """
    6개 임베딩 모델로 문제-코드 의미적 유사도를 계산하고 평균 반환.
    키가 없거나 실패한 모델은 건너뜀. 모두 실패 시 0.80 기본값.
    """
    scorers = [
        ("OpenAI",      _score_openai),
        ("VoyageAI",    _score_voyage),
        ("Cohere",      _score_cohere),
        ("Jina",        _score_jina),
        ("Nomic",       _score_nomic),
        ("ZeroEntropy", _score_zeroentropy),
    ]

    scores = []
    for name, scorer in scorers:
        try:
            score = scorer(problem, code)
            if score is not None:
                scores.append(score)
                print(f"[Semantic] {name}: {score:.4f}")
        except Exception as e:
            print(f"[WARN] {name} 임베딩 실패: {e}")

    if not scores:
        print("[WARN] 모든 임베딩 모델 실패 → 기본값 0.80 사용")
        return 0.80

    avg = sum(scores) / len(scores)
    print(f"[Semantic] 평균 점수: {avg:.4f} ({len(scores)}개 모델)")
    return avg


def save_semantic_result_csv(submissions, problem=""):
    try:
        with open(FINALSCORE_SEMANTIC_INPUT_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["file_name", "semantic_score"])
            for index, submission in enumerate(submissions):
                code = submission.get("code", "")
                if problem and code:
                    score = calculate_semantic_score(problem, code)
                else:
                    score = 0.80
                writer.writerow([make_candidate_file_name(submission.get("model", ""), index + 1), f"{score:.4f}"])
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
