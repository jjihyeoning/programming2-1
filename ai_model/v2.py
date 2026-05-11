import pandas as pd
import numpy as np
import requests
import openai
import voyageai
import cohere
from sklearn.metrics.pairwise import cosine_similarity
import time

class MultiModelEvaluator:
    def __init__(self):
        # API 키 설정 (실행 시 빈칸을 채워주세요)
        self.api_keys = {
            "openai": "________________",
            "voyage": "________________",
            "cohere": "________________",
            "jina": "________________",
            "nomic": "________________",
            "zeroentropy": "________________"
        }

    def calculate_similarity(self, v1, v2):
        """벡터 간 코사인 유사도 계산"""
        v1 = np.array(v1).reshape(1, -1)
        v2 = np.array(v2).reshape(1, -1)
        return float(cosine_similarity(v1, v2)[0][0])

    # 1. OpenAI (text-embedding-3-large)
    def get_openai_score(self, query, code):
        client = openai.OpenAI(api_key=self.api_keys["openai"])
        q_vec = client.embeddings.create(input=[query], model="text-embedding-3-large").data[0].embedding
        c_vec = client.embeddings.create(input=[code], model="text-embedding-3-large").data[0].embedding
        return self.calculate_similarity(q_vec, c_vec)

    # 2. Voyage AI (voyage-code-3)
    def get_voyage_score(self, query, code):
        vo = voyageai.Client(api_key=self.api_keys["voyage"])
        q_vec = vo.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
        c_vec = vo.embed([code], model="voyage-code-3", input_type="document").embeddings[0]
        return self.calculate_similarity(q_vec, c_vec)

    # 3. Cohere (Embed v3/v4 - Multilingual)
    def get_cohere_score(self, query, code):
        co = cohere.Client(self.api_keys["cohere"])
        # 질문은 'search_query', 코드는 'search_document'로 의도 분리
        response = co.embed(
            texts=[query, code],
            model="embed-multilingual-v3.0", 
            input_type="search_query" if query else "search_document" 
        )
        # 실제 구현 시에는 query와 code의 input_type을 각각 호출하는 것이 더 정확함
        q_vec = co.embed(texts=[query], model="embed-multilingual-v3.0", input_type="search_query").embeddings[0]
        c_vec = co.embed(texts=[code], model="embed-multilingual-v3.0", input_type="search_document").embeddings[0]
        return self.calculate_similarity(q_vec, c_vec)

    # 4. Jina AI (jina-embeddings-v3)
    def get_jina_score(self, query, code):
        headers = {"Authorization": f"Bearer {self.api_keys['jina']}", "Content-Type": "application/json"}
        def get_embed(text, task):
            data = {"model": "jina-embeddings-v3", "task": task, "input": [text]}
            res = requests.post("https://api.jina.ai/v1/embeddings", headers=headers, json=data).json()
            return res['data'][0]['embedding']
        return self.calculate_similarity(get_embed(query, "retrieval.query"), get_embed(code, "retrieval.passage"))

    # 5. Nomic (nomic-embed-text-v1.5)
    def get_nomic_score(self, query, code):
        headers = {"Authorization": f"Bearer {self.api_keys['nomic']}", "Content-Type": "application/json"}
        def get_embed(text, task):
            data = {"model": "nomic-embed-text-v1.5", "task_type": task, "texts": [text]}
            res = requests.post("https://api-atlas.nomic.ai/v1/embedding/text", headers=headers, json=data).json()
            return res['embeddings'][0]
        return self.calculate_similarity(get_embed(query, "search_query"), get_embed(code, "search_document"))

    # 6. ZeroEntropy (zembed-1)
    def get_zeroentropy_score(self, query, code):
        # ZeroEntropy는 고성능/저지연 특화 API 구조를 가짐
        url = "https://api.zeroentropy.ai/v1/embeddings" 
        headers = {"Authorization": f"Bearer {self.api_keys['zeroentropy']}", "Content-Type": "application/json"}
        def get_embed(text):
            data = {"model": "zembed-1", "input": [text]}
            res = requests.post(url, headers=headers, json=data).json()
            return res['data'][0]['embedding']
        return self.calculate_similarity(get_embed(query), get_embed(code))

# --- 메인 실행 흐름 ---

if __name__ == "__main__":
    # 1. 테스트 데이터 세팅
    sample_query = "C++에서 이분 탐색(Binary Search)을 사용하여 배열에서 특정 값의 인덱스를 찾는 함수를 작성해줘."
    
    code_candidates = [
        "int search(int arr[], int n, int x) { int l = 0, r = n - 1; while (l <= r) { int m = l + (r - l) / 2; if (arr[m] == x) return m; if (arr[m] < x) l = m + 1; else r = m - 1; } return -1; }", # 정답
        "int binarySearch(int arr[], int l, int r, int x) { if (r >= l) { int mid = l + (r - l) / 2; if (arr[mid] == x) return mid; if (arr[mid] > x) return binarySearch(arr, l, mid - 1, x); return binarySearch(arr, mid + 1, r, x); } return -1; }", # 정답(재귀)
        "int findIndex(int arr[], int n, int x) { for(int i=0; i<n; i++) { if(arr[i] == x) return i; } return -1; }" # 오답(의도 미반영)
    ]

    evaluator = MultiModelEvaluator()
    models_to_test = ["openai", "voyage", "cohere", "jina", "nomic", "zeroentropy"]

    for model_name in models_to_test:
        results = []
        print(f"\n🚀 {model_name.upper()} 모델 평가 시작...")
        
        for i, code in enumerate(code_candidates):
            try:
                # 모델별 점수 계산 함수 동적 호출
                score_func = getattr(evaluator, f"get_{model_name}_score")
                score = score_func(sample_query, code)
                
                results.append({
                    "Model": model_name,
                    "Candidate_ID": f"Code_{i+1}",
                    "Semantic_Score": round(score, 4),
                    "Query": sample_query,
                    "Code_Snippet": code[:60] + "..."
                })
                print(f"   - Code_{i+1} 완료: {score:.4f}")
                time.sleep(0.5) # API 과부하 방지용 짧은 휴식
                
            except Exception as e:
                print(f"   ❌ {model_name} 평가 중 에러 발생: {e}")

        # 2. 개별 모델별 CSV 저장
        if results:
            df = pd.DataFrame(results)
            filename = f"eval_result_{model_name}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"✅ {filename} 저장 완료!")
