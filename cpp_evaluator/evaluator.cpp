//코드를 짜는 과정에서 llm의 도움을 받아 학습의 관점에서 주석을 많이 달았습니다.
#include <windows.h> //코드 안에서 다른 프로그램을 실행하고 관리하기 위한 도구
#include <psapi.h> // memory_score을 계산하기 위한 헤더

#include <algorithm> // 정렬과 최대값 계산에 사용됨.
#include <chrono> // 실행시간 측정에 사용됨.
#include <filesystem> 
#include <fstream> // csv결과 파일을 만들 때 사용됨.
#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#include "evaluator.h"
#include "InputManager.h"
/*현재 중간 제출 버전에서는 테스트케이스 기반 정답 검증 기능을 제외하고, 
코드의 순수 실행 성능 측정에 집중하였다. 
따라서 pass_rate는 산출하지 않으며, 
대신 컴파일 성공 여부, 실행 성공 여부, 실행 시간, 메모리 사용량을 기반으로
time_score와 memory_score를 계산하였다. 
최종 프로젝트 단계에서는 테스트케이스 비교 기능을 추가하여 
pass_rate까지 계산할 수 있도록 확장할 예정이다.*/

using namespace std;
namespace fs = std::filesystem;


vector<string> findCandidateFiles(const string& candidateDir) {
    vector<string> files;

    if (!fs::exists(candidateDir)) {
        cerr << "[ERROR] candidates 폴더가 없습니다: " << candidateDir << endl;
        return files;
    }

    for (const auto& entry : fs::directory_iterator(candidateDir)) {
        if (entry.is_regular_file() && entry.path().extension() == ".cpp") {
            files.push_back(entry.path().string());
        }
    }

    sort(files.begin(), files.end());
    return files;
}

/*
    외부 명령어를 실행하는 함수

    이 함수는 g++ 컴파일 명령어를 실행할 때 사용된다.
    컴파일 결과 로그는 compile_temp_log.txt에 임시 저장한 뒤 문자열로 읽어온다.
*/
bool runCommandWithHiddenWindow(const string& command, string& logOutput, DWORD timeoutMs = 15000) {
    string tempLogFile = "compile_temp_log.txt";
    string fullCommand = "cmd.exe /C " + command + " > " + tempLogFile + " 2>&1";

    STARTUPINFOA si;
    PROCESS_INFORMATION pi;

    ZeroMemory(&si, sizeof(si));
    ZeroMemory(&pi, sizeof(pi));

    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    char* cmdLine = new char[fullCommand.size() + 1];
    strcpy(cmdLine, fullCommand.c_str());

    BOOL created = CreateProcessA(
        NULL,
        cmdLine,
        NULL,
        NULL,
        FALSE,
        CREATE_NO_WINDOW,
        NULL,
        NULL,
        &si,
        &pi
    );

    delete[] cmdLine;

    if (!created) {
        logOutput = "CreateProcess failed.";
        return false;
    }

    DWORD waitResult = WaitForSingleObject(pi.hProcess, timeoutMs);

    if (waitResult == WAIT_TIMEOUT) {
        TerminateProcess(pi.hProcess, 1);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        logOutput = "Compile timeout.";
        return false;
    }

    DWORD exitCode = 1;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    ifstream fin(tempLogFile);
    stringstream buffer;
    buffer << fin.rdbuf();
    logOutput = buffer.str();
    fin.close();

    fs::remove(tempLogFile);

    return exitCode == 0;
}


/* 후보 C++ 코드를 g++로 컴파일하는 함수
sourcePath: candidates 폴더에 있는 원본 .cpp 파일 경로
exePath: build 폴더에 생성될 .exe 파일 경로 */

bool compileCandidate(const string& sourcePath, const string& exePath, string& compileLog) {
    string command = "g++ \"" + sourcePath + "\" -o \"" + exePath + "\" -std=c++17";
    return runCommandWithHiddenWindow(command, compileLog, 15000);
}

/*
    컴파일된 실행 파일을 실행하고 시간과 메모리를 측정하는 함수

    측정 항목:
    - executionTimeMs: 실행 시간(ms)
    - peakMemoryKB: 최대 메모리 사용량(KB)
    - runSuccess: 정상 실행 여부
    - timeout: 시간 초과 여부
*/
CandidateResult runExecutableAndMeasure(const string& exePath, CandidateResult result, DWORD timeoutMs = 5000) {
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;

    ZeroMemory(&si, sizeof(si));
    ZeroMemory(&pi, sizeof(pi));

    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    string command = "cmd.exe /C \"" + exePath + "\"";

    char* cmdLine = new char[command.size() + 1];
    strcpy(cmdLine, command.c_str());

    auto start = chrono::high_resolution_clock::now();

    BOOL created = CreateProcessA(
        NULL,
        cmdLine,
        NULL,
        NULL,
        FALSE,
        CREATE_NO_WINDOW,
        NULL,
        NULL,
        &si,
        &pi
    );

    delete[] cmdLine;

    if (!created) {
        result.runSuccess = false;
        return result;
    }

    size_t peakMemoryKB = 0;
    DWORD waitResult;

    while (true) {
        waitResult = WaitForSingleObject(pi.hProcess, 10);

        PROCESS_MEMORY_COUNTERS pmc;
        if (GetProcessMemoryInfo(pi.hProcess, &pmc, sizeof(pmc))) {
            size_t currentMemoryKB = pmc.PeakWorkingSetSize / 1024;
            peakMemoryKB = max(peakMemoryKB, currentMemoryKB);
        }

        auto now = chrono::high_resolution_clock::now();
        long long elapsedMs = chrono::duration_cast<chrono::milliseconds>(now - start).count();

        if (waitResult == WAIT_OBJECT_0) {
            break;
        }

        if (elapsedMs > timeoutMs) {
            TerminateProcess(pi.hProcess, 1);
            result.timeout = true;
            break;
        }
    }

    auto end = chrono::high_resolution_clock::now();
    result.executionTimeMs = chrono::duration_cast<chrono::milliseconds>(end - start).count();

    DWORD exitCode = 1;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    result.peakMemoryKB = peakMemoryKB;
    result.runSuccess = (!result.timeout && exitCode == 0);

    return result;
}

/*
    실행 시간을 0~1 사이 점수로 변환하는 함수

    시간이 짧을수록 높은 점수를 부여.
*/
double calculateTimeScore(long long timeMs) {
    if (timeMs <= 10) return 1.0;
    if (timeMs <= 50) return 0.9;
    if (timeMs <= 100) return 0.8;
    if (timeMs <= 300) return 0.6;
    if (timeMs <= 700) return 0.4;
    if (timeMs <= 1000) return 0.2;
    return 0.0;
}

/*
    메모리 사용량을 0~1 사이 점수로 변환하는 함수

    메모리를 적게 사용할수록 높은 점수를 부여.
*/
double calculateMemoryScore(size_t memoryKB) {
    if (memoryKB <= 1024) return 1.0;
    if (memoryKB <= 4096) return 0.9;
    if (memoryKB <= 8192) return 0.8;
    if (memoryKB <= 16384) return 0.6;
    if (memoryKB <= 32768) return 0.4;
    if (memoryKB <= 65536) return 0.2;
    return 0.0;
}

/*
    후보 코드 하나를 평가하는 함수 ****

    이 함수는 다음 순서로 동작한다.
    1. 후보 코드 파일명과 경로 설정
    2. build 폴더 생성
    3. g++로 컴파일
    4. 실행 파일 실행
    5. 실행 시간과 메모리 측정
    6. time_score, memory_score 계산

    단, 이 함수는 final_score나 performance_score를 계산하지 않는다.
*/
CandidateResult evaluateCandidate(const string& sourcePath) {
    CandidateResult result;

    fs::path pathObj(sourcePath);

    result.fileName = pathObj.filename().string();
    result.sourcePath = sourcePath;

    string baseName = pathObj.stem().string();

    fs::create_directories("build");

    result.exePath = "build\\" + baseName + ".exe";

    cout << "\n==============================\n";
    cout << "[평가 시작] " << result.fileName << endl;

    result.compileSuccess = compileCandidate(
        result.sourcePath,
        result.exePath,
        result.compileLog
    );

    if (!result.compileSuccess) {
        cout << "[컴파일 실패] " << result.fileName << endl;

        result.runSuccess = false;
        result.timeout = false;

        result.semanticScore = 0.0;
        result.passRate = 0.0;
        result.timeScore = 0.0;
        result.memoryScore = 0.0;

        return result;
    }

    cout << "[컴파일 성공] " << result.fileName << endl;

    result = runExecutableAndMeasure(result.exePath, result, 5000);

    if (!result.runSuccess) {
        if (result.timeout) {
            cout << "[실행 실패] 시간 초과" << endl;
        }
        else {
            cout << "[실행 실패] 런타임 오류 또는 비정상 종료" << endl;
        }

        result.semanticScore = 0.0;
        result.passRate = 0.0;
        result.timeScore = 0.0;
        result.memoryScore = 0.0;

        return result;
    }

    result.semanticScore = 0.0;
    result.passRate = 1.0;
    result.timeScore = calculateTimeScore(result.executionTimeMs);
    result.memoryScore = calculateMemoryScore(result.peakMemoryKB);

    cout << fixed << setprecision(2);
    cout << "[실행 성공]" << endl;
    cout << "실행 시간: " << result.executionTimeMs << "ms" << endl;
    cout << "최대 메모리 사용량: " << result.peakMemoryKB << "KB" << endl;
    cout << "semantic_score: " << result.semanticScore << "  // placeholder" << endl;
    cout << "pass_rate: " << result.passRate << "  // placeholder" << endl;
    cout << "time_score: " << result.timeScore << endl;
    cout << "memory_score: " << result.memoryScore << endl;

    return result;
}

/*
    결과를 CSV 파일로 저장하는 함수

    CSV 형식:
    file_name,semantic_score,pass_rate,time_score,memory_score 
    --추후에 2단계 제작자와 csv파일 형식을 더 논의해 볼 예정

    semantic_score와 pass_rate는 3단계(현재단계)에서는 계산하지 않으므로 0.00으로 저장된다.
    4단계 담당자가 이 CSV를 기반으로 semantic_score, pass_rate를 채우고 final_score를 계산할 수 있다.
*/
void writeCsvResult(const vector<CandidateResult>& results, const string& outputPath) {
    fs::create_directories("results");

    ofstream fout(outputPath);

    if (!fout.is_open()) {
        cerr << "[ERROR] CSV 파일을 생성할 수 없습니다." << endl;
        return;
    }

    fout << "file_name,semantic_score,pass_rate,time_score,memory_score,runtime_ms,memory_kb\n";

    fout << fixed << setprecision(2);

    for (const auto& r : results) {
        fout << r.fileName << ",";
        fout << r.semanticScore << ",";
        fout << r.passRate << ",";
        fout << r.timeScore << ",";
        fout << r.memoryScore << ",";
        fout << r.executionTimeMs << ",";
        fout << r.peakMemoryKB << "\n";
    }

    fout.close();
}


int main() {
    try {
        prepareCandidatesFromRequestJson();
    }
    catch (const exception& e) {
        cerr << "[ERROR] 후보 코드 준비 실패: " << e.what() << endl;
        return 1;
    }

    cout << "========================================\n";
    cout << " C++ Execution Metrics Evaluator\n";
    cout << "========================================\n";

    string candidateDir = "candidates";
    string resultCsvPath = "results/execution_metrics.csv";

    vector<string> candidateFiles = findCandidateFiles(candidateDir);

    if (candidateFiles.empty()) {
        cerr << "[ERROR] 평가할 후보 코드가 없습니다." << endl;
        return 1;
    }

    cout << "[INFO] 후보 코드 개수: " << candidateFiles.size() << endl;

    vector<CandidateResult> results;

    for (const string& sourcePath : candidateFiles) {
        CandidateResult result = evaluateCandidate(sourcePath);
        results.push_back(result);
    }

    writeCsvResult(results, resultCsvPath);

    cout << "\n[INFO] CSV 결과 저장 완료: " << resultCsvPath << endl;
    cout << "[INFO] CSV 형식: file_name,semantic_score,pass_rate,time_score,memory_score" << endl;

    cout << "\n3단계 실행 평가가 완료되었습니다." << endl;

    return 0;
}

