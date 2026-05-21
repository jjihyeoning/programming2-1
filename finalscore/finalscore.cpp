#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <unordered_map>
#include <algorithm>
#include <iomanip>
using namespace std;

/*

    semantic_score는 AI 기반 의미 분석 결과,
    pass_rate, time_score, memory_score는
    실행 평가 단계에서 전달받은 성능 지표임

    최종적으로 모든 평가 지표를 통합해서
    final_score를 계산하고 후보 코드 비교
*/
struct Candidate {
    string file_name;

    double semantic_score = 0.0;
    double pass_rate = 0.0;
    double time_score = 0.0;
    double memory_score = 0.0;

    double final_score = 0.0;
};

/*
    현재 가중치는 중간 구현 단계에서 사용하는 임시값입니다

    우선 코드가 정답이어야 하는 것이 최우선이므로 pass rate가 가장 높은 가중치를 받을 예정

    이후 AI 의미 적합도와 실행 성능을 함께 반영

    최종 단계에서는 실험 결과 및 평가 기준에 따라
    가중치가 조정될 수 있도록 분리하여 관리
*/
const double WEIGHT_SEMANTIC = 0.25;
const double WEIGHT_PASS = 0.50;
const double WEIGHT_TIME = 0.15;
const double WEIGHT_MEMORY = 0.10;

/*
    모든 평가 지표는 공정한 비교를 위해 0~1 범위로 정함
    입력범위 제한
*/
bool isValidScore(double score) {
    return score >= 0.0 && score <= 1.0;
}

/*
    2단계와 3단계에서 전달받은 평가 지표를 하나의 FinalScore로 통합하는 함수
    

    semantic_score:
    문제 의도와 코드 의미의 적합도

    pass_rate:
    테스트케이스 기반 정답률

    time_score:
    실행 시간 기반 성능 점수

    memory_score:
    메모리 효율 기반 성능 점수
*/
double calculateFinalScore(const Candidate& c) {
    return c.semantic_score * WEIGHT_SEMANTIC
        + c.pass_rate * WEIGHT_PASS
        + c.time_score * WEIGHT_TIME
        + c.memory_score * WEIGHT_MEMORY;
}

/*
   앞선 과정에서 csv파일로 성능을 받아서 쓸 예정임
   따라서 csv를 필요에 맞게 정리하는 과정이 필요함.
  
    CSV 파일의 한 줄을 ',' 기준으로 분리하는 함수
*/
vector<string> splitCSVLine(const string& line) {
    vector<string> result;
    string token;
    stringstream ss(line);

    while (getline(ss, token, ',')) {
        result.push_back(token);
    }

    return result;
}

/*
    2단계 AI 의미 분석 결과 CSV를 읽어오는 함수

    semantic_result.csv에는
    각 후보 코드의 semantic_score가 저장되어 있고
    file_name을 기준으로 매칭하기 위해 map 형태로 관리한다.
*/
unordered_map<string, double> readSemanticCSV(const string& filename) {

    unordered_map<string, double> semanticMap;

    ifstream file(filename);

    if (!file.is_open()) {
        cout << "오류: " << filename << " 파일을 열 수 없습니다.\n";
        return semanticMap;
    }

    string line;

    getline(file, line);

    while (getline(file, line)) {

        vector<string> cols = splitCSVLine(line);

        if (cols.size() < 2) {
            continue;
        }

        string file_name = cols[0];
        double semantic_score = stod(cols[1]);

        /*
            semantic_score는 정규화된 점수 체계를 사용하므로
            범위를 벗어난 데이터는 제외한다.
        */
        if (!isValidScore(semantic_score)) {

            cout << "경고: "
                << file_name
                << "의 semantic_score 값이 올바르지 않아 제외합니다.\n";

            continue;
        }

        semanticMap[file_name] = semantic_score;
    }

    file.close();

    return semanticMap;
}

/*
    3단계 실행 평가 결과 CSV를 읽어오는 함수

    execution_result.csv에는
    pass_rate, time_score, memory_score가 저장되어 있고
    file_name 기준으로 semantic_score와 결합한다.

*/
vector<Candidate> readExecutionCSV(
    const string& filename,
    const unordered_map<string, double>& semanticMap
) {

    vector<Candidate> candidates;

    ifstream file(filename);

    if (!file.is_open()) {
        cout << "오류: " << filename << " 파일을 열 수 없습니다.\n";
        return candidates;
    }

    string line;

    getline(file, line);

    while (getline(file, line)) {

        vector<string> cols = splitCSVLine(line);

        if (cols.size() < 9) {
            continue;
        }

        Candidate c;

        c.file_name = cols[0];

        /*
            semantic_result.csv와 execution_result.csv를 file_name 기준으로 연결
            .

            semantic_score가 존재하지 않는 후보 코드는 제외시킴
        */
        if (semanticMap.find(c.file_name) == semanticMap.end()) {

            cout << "경고: "
                << c.file_name
                << "의 semantic_score가 없어 제외합니다.\n";

            continue;
        }

        c.semantic_score = semanticMap.at(c.file_name);

        c.pass_rate = stod(cols[6]);
        c.time_score = stod(cols[7]);
        c.memory_score = stod(cols[8]);

        
          //  실행 평가 결과도 비정상적인 값은 제외한다.
        
        if (!isValidScore(c.pass_rate) ||
            !isValidScore(c.time_score) ||
            !isValidScore(c.memory_score)) {

            cout << "경고: "
                << c.file_name
                << "의 실행 평가 점수가 올바르지 않아 제외합니다.\n";

            continue;
        }

      //   모든 평가 지표가 준비되면 최종 점수를 계산하여 후보 목록에 저장한다.
            
        
        c.final_score = calculateFinalScore(c);

        candidates.push_back(c);
    }

    file.close();

    return candidates;
}

int main() {

  
      //  2단계와 3단계에서 생성된 CSV 파일을 입력으로 사용한다.
    
    string semanticFile = "semantic_result.csv";
    string executionFile = "execution_result.csv";

    /*
        semantic_result.csv에서 semantic_score를 읽고,
        execution_result.csv의 실행 평가 결과와 결합한다.
    */
    unordered_map<string, double> semanticMap =
        readSemanticCSV(semanticFile);

    vector<Candidate> candidates =
        readExecutionCSV(executionFile, semanticMap);

    if (candidates.empty()) {

        cout << "평가할 후보 코드가 없습니다.\n";

        return 0;
    }

    
      //  FinalScore 기준으로 후보 코드를 내림차순 정렬한다.

    
 
    sort(candidates.begin(), candidates.end(),

        [](const Candidate& a, const Candidate& b) {

            return a.final_score > b.final_score;
        }
    );

    cout << "\n===== 최종 평가 결과 =====\n";

    cout << fixed << setprecision(4);

    /*
        후보 코드별 최종 순위와 세부 평가 지표를 출력
        이를 통해 단순 최종 선택만이 아니라
        각 AI 모델 응답 간 성능 차이 비교 가능
    */
    for (int i = 0; i < candidates.size(); i++) {

        cout << i + 1 << "위 | "
            << candidates[i].file_name
            << " | FinalScore: " << candidates[i].final_score
            << " | semantic: " << candidates[i].semantic_score
            << " | pass: " << candidates[i].pass_rate
            << " | time: " << candidates[i].time_score
            << " | memory: " << candidates[i].memory_score
            << '\n';
    }

    
     //   정렬 이후 가장 앞에 위치한 후보가 평가 결과가 가장 높은 코드임
     //   최종 코드로 제출시킴
    
    cout << "\n최종 선택 코드: "
        << candidates[0].file_name << '\n';

    cout << "최종 점수: "
        << candidates[0].final_score << '\n';

    return 0;
}