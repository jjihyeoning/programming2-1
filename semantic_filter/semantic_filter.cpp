#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

// 후보 코드 하나의 semantic 점수 합계와 성공한 평가 모델 수를 저장
struct Result {
    string model;
    double sum = 0.0;
    int count = 0;
};

// CSV 한 줄을 쉼표 기준으로 분리
vector<string> split(string line) {
    vector<string> data;
    string value;
    stringstream ss(line);

    while (getline(ss, value, ',')) {
        data.push_back(value);
    }

    return data;
}

int main() {
    // semantic 평균 점수가 이 값 이상이면 실행 성능 평가 대상으로 통과
    const double threshold = 0.60;

    // AI 평가 결과 입력 파일
    ifstream input("semantic_filter/raw_semantic_scores.csv");

    // cpp_evaluator에 넘길 통과 후보 목록
    ofstream passed("semantic_filter/passed_candidates.csv");

    // finalscore에서 나중에 사용할 semantic 점수
    ofstream semanticResult("finalscore/semantic_result.csv");

    // semantic 단계에서 제거된 후보 목록
    ofstream filtered("semantic_filter/filtered_out.csv");

    if (!input.is_open()) {
        cout << "raw_semantic_scores.csv 파일을 찾을 수 없습니다." << endl;
        return 1;
    }

    // 파일명별로 semantic 점수를 모아서 저장
    map<string, Result> results;

    string line;
    getline(input, line);  // header 제외

    // 성공한 AI 평가 점수만 후보 코드별로 합산
    while (getline(input, line)) {
        vector<string> row = split(line);

        /*
            row[0] = file_name
            row[1] = code_model
            row[2] = provider
            row[3] = score
            row[4] = status
        */

        if (row.size() < 5) {
            continue;
        }

        string fileName = row[0];
        string codeModel = row[1];
        string score = row[3];
        string status = row[4];

        results[fileName].model = codeModel;

        // 평가에 성공한 점수만 평균 계산에 포함
        if (status == "success") {
            results[fileName].sum += stod(score);
            results[fileName].count++;
        }
    }

    // 결과 CSV header 작성
    passed << "file_name,code_model,semantic_score\n";
    semanticResult << "file_name,semantic_score\n";
    filtered << "file_name,code_model,semantic_score\n";

    // 점수는 소수점 넷째 자리까지 출력
    cout << fixed << setprecision(4);
    passed << fixed << setprecision(4);
    semanticResult << fixed << setprecision(4);
    filtered << fixed << setprecision(4);

    // 후보별 평균 점수를 계산하여 통과 또는 제거
    for (auto& item : results) {
        string fileName = item.first;
        Result result = item.second;

        // 성공한 평가 모델이 하나도 없는 후보는 제외
        if (result.count == 0) {
            continue;
        }

        double average = result.sum / result.count;

        cout << result.model
             << " 평균 점수: "
             << average;

        if (average >= threshold) {
            // 다음 단계인 cpp_evaluator가 평가할 후보 목록
            passed << fileName << ","
                   << result.model << ","
                   << average << "\n";

            // cpp_evaluator 이후 finalscore가 사용할 semantic 점수
            semanticResult << fileName << ","
                           << average << "\n";

            cout << " -> 통과" << endl;
        }
        else {
            // 의미 적합도가 낮아 실행 평가 전에 제거
            filtered << fileName << ","
                     << result.model << ","
                     << average << "\n";

            cout << " -> 제거" << endl;
        }
    }

    input.close();
    passed.close();
    semanticResult.close();
    filtered.close();

    cout << "\nsemantic 필터링 완료" << endl;

    return 0;
}