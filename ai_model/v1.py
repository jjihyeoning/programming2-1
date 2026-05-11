import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# 1. API 기반 모델들 (각 서비스의 SDK 설치 필요: pip install openai voyageai cohere jina)
import openai
import voyageai
import cohere
import requests
import json

class MultiModelEvaluator:
    def __init__(self):
        # API 키 설정 (빈칸)
        self.api_keys = {
            "openai": "________________",
            "voyage": "________________",
            "cohere": "________________",
            "jina": "________________",
            "nomic": "________________",
            "zeroentropy": "________________"
        }

    def get_openai_embedding(self, text):
        client = openai.OpenAI(api_key=self.api_keys["openai"])
        response = client.embeddings.create(
            input=[text],
            model="text-embedding-3-large"
        )
        return response.data[0].embedding

    def get_voyage_embedding(self, text):
        vo = voyageai.Client(api_key=self.api_keys["voyage"])
        # 코드 분석에 최적화된 voyage-code-3 사용
        result = vo.embed([text], model="voyage-code-3", input_type="document")
        return result.embeddings[0]

    def get_cohere_embedding(self, text):
        co = cohere.Client(self.api_keys["cohere"])
        # v4 모델 사용
        response = co.embed(
            texts=[text],
            model="embed-multilingual-v3.0", # v4/v3 계열 선택
            input_type="search_document"
        )
        return response.embeddings[0]

    def get_jina_embedding(self, text):
        # Jina는 보통 HTTP 요청이나 전용 SDK 사용
        import requests
        url = "https://api.jina.ai/v1/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_keys['jina']}"
        }
        data = {
            "model": "jina-embeddings-v3",
            "task": "code_search", # 코드 검색 특화 태스크
            "input": [text]
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()['data'][0]['embedding']
    def get_nomic_embedding(self, text):
        """
        Nomic Embed v1.5 구현
        참고: nomic 라이브러리를 사용하거나 직접 API 호출 가능
        """
        url = "https://api-atlas.nomic.ai/v1/embedding/text"
        headers = {
            "Authorization": f"Bearer {self.api_keys['nomic']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "nomic-embed-text-v1.5",
            "texts": [text],
            "task_type": "search_document" # 질문일 경우 'search_query'로 가변적 설정 권장
        }
        
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['embeddings'][0]
        else:
            raise Exception(f"Nomic API Error: {response.text}")

    def get_zeroentropy_embedding(self, text):
        """
        ZeroEntropy zembed-1 구현
        주로 고성능 저지연 API를 제공합니다.
        """
        url = "https://api.zeroentropy.ai/v1/embeddings" # 실제 엔드포인트는 가입 후 확인되는 URL 사용
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_keys['zeroentropy']}"
        }
        data = {
            "model": "zembed-1",
            "input": [text]
        }
        
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['data'][0]['embedding']
        else:
            raise Exception(f"ZeroEntropy API Error: {response.text}")


def calculate_similarity(v1, v2):
    """두 벡터 간의 코사인 유사도를 계산합니다."""
    v1 = np.array(v1).reshape(1, -1)
    v2 = np.array(v2).reshape(1, -1)
    return cosine_similarity(v1, v2)[0][0]

# --- 실행 예시 ---
if __name__ == "__main__":
    evaluator = MultiModelEvaluator()
    
    question = "이분 탐색을 이용해 배열에서 타겟 숫자의 인덱스를 찾는 C++ 코드를 짜줘."
    code_answer = """
    int binarySearch(int arr[], int l, int r, int x) {
        while (l <= r) {
            int m = l + (r - l) / 2;
            if (arr[m] == x) return m;
            if (arr[m] < x) l = m + 1;
            else r = m - 1;
        }
        return -1;
    }
    """

    # 예시: Voyage 모델로 유사도 측정
    try:
        q_vec = evaluator.get_voyage_embedding(question)
        c_vec = evaluator.get_voyage_embedding(code_answer)
        
        score = calculate_similarity(q_vec, c_vec)
        print(f"Voyage-code-3 Semantic Score: {score:.4f}")
    except Exception as e:
        print("API 키가 설정되지 않아 실행할 수 없습니다. 빈칸을 채워주세요.")
