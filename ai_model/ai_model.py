import pandas as pd
import numpy as np
import requests
import openai
import voyageai
import cohere
from sklearn.metrics.pairwise import cosine_similarity
import time

import os
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(ENV_PATH)

class Performance_measurement:
    def __init__(self):
        # API 키 입력 (최종결과물에 첨부하여 실행할 예정)
        self.api_keys = {
    "openai": os.getenv("OPENAI_API_KEY", ""),
    "voyage": os.getenv("VOYAGE_API_KEY", ""),
    "cohere": os.getenv("COHERE_API_KEY", ""),
    "jina": os.getenv("JINA_API_KEY", ""),
    "nomic": os.getenv("NOMIC_API_KEY", ""),
    "zeroentropy": os.getenv("ZEROENTROPY_API_KEY", "")
    }

    # cosine_similarity 함수로 두 벡터 간 유사도 측정
    # (임베딩 모델들에 사용 예정)
    def calculate_similarity(self, q, c):
        q = np.array(q).reshape(1, -1)
        c = np.array(c).reshape(1, -1)
        return float(cosine_similarity(q, c)[0][0])
    

    # 1.OpenAI (text-embedding-3-large)
    def get_openai_score(self, 질문, 코드):
        client = openai.OpenAI(api_key=self.api_keys["openai"])
        질문vector = client.embeddings.create(input=[질문], model="text-embedding-3-large").data[0].embedding
        코드vector = client.embeddings.create(input=[코드], model="text-embedding-3-large").data[0].embedding
        return self.calculate_similarity(질문vector, 코드vector)

    # 2.VoyageAI (voyage-code-3)
    def get_voyage_score(self, 질문, 코드):
        vo = voyageai.Client(api_key=self.api_keys["voyage"])
        질문vector = vo.embed([질문], model="voyage-code-3", input_type="query").embeddings[0]
        코드vector = vo.embed([코드], model="voyage-code-3", input_type="document").embeddings[0]
        return self.calculate_similarity(질문vector, 코드vector)

    # 3.Cohere (Embed v3/v4 - Multilingual)
    def get_cohere_score(self, 질문, 코드):
        co = cohere.Client(self.api_keys["cohere"])
        # 질문은 search_query, 코드는 search_document로 input_type 분리
        response = co.embed(
            texts=[질문, 코드],
            model="embed-multilingual-v3.0", 
            input_type="search_query" if 질문 else "search_document" 
        )
        '''
        Cohere에서는 모델이 텍스트를 어떤 용도로 사용하는지 입력하게 되어있음.
        search_query : 질문이나 검색어
        search_document : 질문에 대한 답변이나 검색 대상
        따라서 프로젝트에 사용하기 적절하도록 질문에는 input_type을 search_query로,
        답변인 코드에는 search_document로 input_type을 따로 지정해주어서 오류가 없게 하였음.
        '''
        질문vector = co.embed(texts=[질문], model="embed-multilingual-v3.0", input_type="search_query").embeddings[0]
        코드vector = co.embed(texts=[코드], model="embed-multilingual-v3.0", input_type="search_document").embeddings[0]
        return self.calculate_similarity(질문vector, 코드vector)

    # 4.Jina AI (jina-embeddings-v3)
    def get_jina_score(self, 질문, 코드):
        headers = {"Authorization": f"Bearer {self.api_keys['jina']}", "Content-Type": "application/json"}
        def get_embed(text, task):
            data = {"model": "jina-embeddings-v3", "task": task, "input": [text]}
            res = requests.post("https://api.jina.ai/v1/embeddings", headers=headers, json=data).json()
            return res['data'][0]['embedding']
        return self.calculate_similarity(get_embed(질문, "retrieval.query"), get_embed(코드, "retrieval.passage"))

    # 5.Nomic (nomic-embed-text-v1.5)
    def get_nomic_score(self, 질문, 코드):
        headers = {"Authorization": f"Bearer {self.api_keys['nomic']}", "Content-Type": "application/json"}
        def get_embed(text, task):
            data = {"model": "nomic-embed-text-v1.5", "task_type": task, "texts": [text]}
            res = requests.post("https://api-atlas.nomic.ai/v1/embedding/text", headers=headers, json=data).json()
            return res['embeddings'][0]
        return self.calculate_similarity(get_embed(질문, "search_query"), get_embed(코드, "search_document"))

    # 6.ZeroEntropy (zembed-1)
    def get_zeroentropy_score(self, 질문, 코드):
        url = "https://api.zeroentropy.ai/v1/embeddings" 
        headers = {"Authorization": f"Bearer {self.api_keys['zeroentropy']}", "Content-Type": "application/json"}
        def get_embed(text):
            data = {"model": "zembed-1", "input": [text]}
            res = requests.post(url, headers=headers, json=data).json()
            return res['data'][0]['embedding']
        return self.calculate_similarity(get_embed(질문), get_embed(코드))


# --- 메인 실행 ---
if __name__ == "__main__":
    '''
    테스트 데이터로 C++에서 이진탐색 이용해 인덱스 출력하는 질문과 
    질문에 대한 답변 코드 3개 넣음
    이 테스트 데이터는 차후 LLM 질문/응답 데이터로 수정할 예정임.
    '''
    sample_query = "C++에서 Binary Search를 사용하여 배열에서 특정 값의 인덱스를 찾는 함수를 작성해줘"
    sample_code = [
        "int search(int arr[], int n, int x) { int l = 0, r = n - 1; while (l <= r) { int m = l + (r - l) / 2; if (arr[m] == x) return m; if (arr[m] < x) l = m + 1; else r = m - 1; } return -1; }", # 정답
        "int binarySearch(int arr[], int l, int r, int x) { if (r >= l) { int mid = l + (r - l) / 2; if (arr[mid] == x) return mid; if (arr[mid] > x) return binarySearch(arr, l, mid - 1, x); return binarySearch(arr, mid + 1, r, x); } return -1; }", # 정답(재귀)
        "int findIndex(int arr[], int n, int x) { for(int i=0; i<n; i++) { if(arr[i] == x) return i; } return -1; }" # 오답(의도 미반영)
    ]

    evaluator = Performance_measurement()
    models = ["openai", "voyage", "cohere", "jina", "nomic", "zeroentropy"]

    # 이전 실행에서 만들어진 모델별 결과 CSV 삭제
    # 이번 실행에서 실패한 모델의 오래된 결과가 섞이지 않도록 하기 위함
    for old_csv in Path.cwd().glob("eval_result_*.csv"):
        old_csv.unlink()

    raw_output_path = (
        Path(__file__).resolve().parent.parent
        / "semantic_filter"
        / "raw_semantic_scores.csv"
    )

    if raw_output_path.exists():
        raw_output_path.unlink()

    for model_name in models:
        results = []
        print(f"\n★ {model_name.upper()} 평가 시작")
        for i, code in enumerate(sample_code):
            try:
                # 모델별 점수 계산 함수 호출
                score_func = getattr(evaluator, f"get_{model_name}_score")
                score = score_func(sample_query, code)
                results.append({
                    "Model": model_name,
                    "Code Name": f"Code{i+1}",
                    "질문-코드 유사도": round(score, 4),
                    "질문": sample_query,
                    "코드 개요": code[:60] + "..."
                })
                print(f"   - Code{i+1} 완료: {score:.4f}")
                time.sleep(0.5) # 과부하 방지
                
            except Exception as e:
                print(f"   - {model_name} 에러 {e}")

        # 모델별 CSV 저장
        if results:
            df = pd.DataFrame(results)
            filename = f"eval_result_{model_name}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"☆ {filename} 저장 완료")


# --- 모델별 CSV를 하나의 raw_semantic_scores.csv로 통합 ---
# 이부분을 semantic_filter.cpp로 받아서 계산할 예정
if __name__ == "__main__":
    provider_names = [
        "openai",
        "voyage",
        "cohere",
        "jina",
        "nomic",
        "zeroentropy",
    ]

    # 현재 단독 테스트 기준 매핑
    # 이후 backend에서 실제 LLM 후보를 넘기게 되면 이 매핑은 submissions 기반으로 변경할 예정
    candidate_map = {
        "Code1": {
            "file_name": "code_Gemini.cpp",
            "code_model": "Gemini",
        },
        "Code2": {
            "file_name": "code_GPT.cpp",
            "code_model": "GPT",
        },
        "Code3": {
            "file_name": "code_Claude.cpp",
            "code_model": "Claude",
        },
    }

    result_directory = Path.cwd()

    raw_output_path = (
        Path(__file__).resolve().parent.parent
        / "semantic_filter"
        / "raw_semantic_scores.csv"
    )
    raw_output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_rows = []

    for provider_name in provider_names:
        provider_csv_path = result_directory / f"eval_result_{provider_name}.csv"

        # 해당 공급자에서 성공적으로 생성된 점수만 담음
        successful_scores = {}

        if provider_csv_path.exists():
            try:
                provider_df = pd.read_csv(
                    provider_csv_path,
                    encoding="utf-8-sig",
                )

                for _, row in provider_df.iterrows():
                    code_name = str(row["Code Name"]).strip()
                    score = row["질문-코드 유사도"]

                    if code_name in candidate_map and pd.notna(score):
                        successful_scores[code_name] = round(float(score), 4)

            except Exception as error:
                print(
                    f"[RAW CSV] {provider_name} 결과 파일 읽기 실패: {error}"
                )

        # 성공한 점수는 success, 없는 점수는 failed로 통합 파일에 기록
        for code_name, candidate_info in candidate_map.items():
            if code_name in successful_scores:
                raw_rows.append({
                    "file_name": candidate_info["file_name"],
                    "code_model": candidate_info["code_model"],
                    "provider": provider_name,
                    "score": successful_scores[code_name],
                    "status": "success",
                })
            else:
                raw_rows.append({
                    "file_name": candidate_info["file_name"],
                    "code_model": candidate_info["code_model"],
                    "provider": provider_name,
                    "score": "",
                    "status": "failed",
                })

    raw_df = pd.DataFrame(
        raw_rows,
        columns=[
            "file_name",
            "code_model",
            "provider",
            "score",
            "status",
        ],
    )

    raw_df.to_csv(
        raw_output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(" 통합 Semantic 원시 점수 CSV 생성 완료")
    print(f"[INFO] 저장 위치: {raw_output_path}")
    print(raw_df.to_string(index=False))