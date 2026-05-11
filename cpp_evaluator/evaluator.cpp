#include <windows.h> //코드 안에서 다른 프로그램을 실행하고 관리하기 위한 도구
#include <psapi.h> //memory_score을 계산하기 위한 헤더
#include <algorithm> //정렬과 최댓값 계산에 사용됨. 
#include <chrono> //실행시간 측정에 사용됨. 
#include <filesystem>
#include <fstream> //csv결과 파일을 만들 때 사용됨. 
#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
/*현재 중간 제출 버전에서는 테스트케이스 기반 정답 검증 기능을 제외하고, 
코드의 순수 실행 성능 측정에 집중하였다. 
따라서 pass_rate는 산출하지 않으며, 
대신 컴파일 성공 여부, 실행 성공 여부, 실행 시간, 메모리 사용량을 기반으로
time_score와 memory_score를 계산하였다. 
최종 프로젝트 단계에서는 테스트케이스 비교 기능을 추가하여 
pass_rate까지 계산할 수 있도록 확장할 예정이다.*/

using namespace std;
namespace fs = std::filesystem;

struct CandidateResult {
    string fileName;
    string sourcePath;
    string exePath;

    bool compileSuccess = false;
    bool runSuccess = false;
    bool timeout = false;

    long long executionTimeMs = 0;
    size_t peakMemoryKB = 0;

    double timeScore = 0.0;
    double memoryScore = 0.0;
    double performanceScore = 0.0;

    string compileLog;
}; //후보 코드의 평과 결과를 저장하는 구조체

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
    ); /*C++ 기본 문법만으로는 외부 실행 파일의 메모리 사용량을 
    직접 측정하기 어렵기 때문에,
    Windows에서 제공하는 API를 활용해 실행 중인 프로세스의 메모리 정보를 
    가져오도록 구현했다. */

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

bool compileCandidate(const string& sourcePath, const string& exePath, string& compileLog) {
    string command = "g++ \"" + sourcePath + "\" -o \"" + exePath + "\" -std=c++17";
    return runCommandWithHiddenWindow(command, compileLog, 15000);
}

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

double calculateTimeScore(long long timeMs) {
    if (timeMs <= 10) return 1.0;
    if (timeMs <= 50) return 0.9;
    if (timeMs <= 100) return 0.8;
    if (timeMs <= 300) return 0.6;
    if (timeMs <= 700) return 0.4;
    if (timeMs <= 1000) return 0.2;
    return 0.0;
}

double calculateMemoryScore(size_t memoryKB) {
    if (memoryKB <= 1024) return 1.0;
    if (memoryKB <= 4096) return 0.9;
    if (memoryKB <= 8192) return 0.8;
    if (memoryKB <= 16384) return 0.6;
    if (memoryKB <= 32768) return 0.4;
    if (memoryKB <= 65536) return 0.2;
    return 0.0;
}

double calculatePerformanceScore(double timeScore, double memoryScore) {
    return timeScore * 0.6 + memoryScore * 0.4;
}

CandidateResult evaluateCandidate(const string& sourcePath) {
    CandidateResult result;

    fs::path pathObj(sourcePath);

    result.fileName = pathObj.filename().string();
    result.sourcePath = sourcePath;

    string baseName = pathObj.stem().string();

    fs::create_directories("build");

    result.exePath = "build/" + baseName + ".exe";

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
        result.timeScore = 0.0;
        result.memoryScore = 0.0;
        result.performanceScore = 0.0;
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

        result.timeScore = 0.0;
        result.memoryScore = 0.0;
        result.performanceScore = 0.0;
        return result;
    }

    result.timeScore = calculateTimeScore(result.executionTimeMs);
    result.memoryScore = calculateMemoryScore(result.peakMemoryKB);
    result.performanceScore = calculatePerformanceScore(
        result.timeScore,
        result.memoryScore
    );

    cout << fixed << setprecision(4);
    cout << "[실행 성공]" << endl;
    cout << "실행 시간: " << result.executionTimeMs << "ms" << endl;
    cout << "최대 메모리 사용량: " << result.peakMemoryKB << "KB" << endl;
    cout << "time_score: " << result.timeScore << endl;
    cout << "memory_score: " << result.memoryScore << endl;
    cout << "performance_score: " << result.performanceScore << endl;

    return result;
}

void writeCsvResult(const vector<CandidateResult>& results, const string& outputPath) {
    fs::create_directories("results");

    ofstream fout(outputPath);

    if (!fout.is_open()) {
        cerr << "[ERROR] CSV 파일을 생성할 수 없습니다." << endl;
        return;
    }

    fout << "file_name,compile_success,run_success,timeout,";
    fout << "execution_time_ms,peak_memory_kb,";
    fout << "time_score,memory_score,performance_score\n";

    fout << fixed << setprecision(4);

    for (const auto& r : results) {
        fout << r.fileName << ",";
        fout << (r.compileSuccess ? "true" : "false") << ",";
        fout << (r.runSuccess ? "true" : "false") << ",";
        fout << (r.timeout ? "true" : "false") << ",";
        fout << r.executionTimeMs << ",";
        fout << r.peakMemoryKB << ",";
        fout << r.timeScore << ",";
        fout << r.memoryScore << ",";
        fout << r.performanceScore << "\n";
    }

    fout.close();
}

void printBestCandidate(const vector<CandidateResult>& results) {
    int bestIndex = -1;
    double bestScore = -1.0;

    for (int i = 0; i < (int)results.size(); i++) {
        if (results[i].performanceScore > bestScore) {
            bestScore = results[i].performanceScore;
            bestIndex = i;
        }
    }

    cout << "\n==============================\n";
    cout << "[최종 성능 비교 결과]\n";

    if (bestIndex == -1 || bestScore <= 0.0) {
        cout << "선택 가능한 후보 코드가 없습니다." << endl;
        return;
    }

    const CandidateResult& best = results[bestIndex];

    cout << "Best Candidate: " << best.fileName << endl;
    cout << fixed << setprecision(4);
    cout << "Performance Score: " << best.performanceScore << endl;
    cout << "Execution Time: " << best.executionTimeMs << "ms" << endl;
    cout << "Peak Memory: " << best.peakMemoryKB << "KB" << endl;
}

int main() {
    cout << "========================================\n";
    cout << " C++ Performance Measurement Engine\n";
    cout << "========================================\n";

    string candidateDir = "candidates";
    string resultCsvPath = "results/performance_result.csv";

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

    printBestCandidate(results);

    cout << "\n성능 측정이 완료되었습니다." << endl;

    return 0;
}