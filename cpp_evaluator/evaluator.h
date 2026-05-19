#ifndef EVALUATOR_H
#define EVALUATOR_H

#include <windows.h>

#include <cstddef>
#include <string>
#include <vector>

struct CandidateResult {
    std::string fileName;
    std::string sourcePath;
    std::string exePath;

    bool compileSuccess = false;
    bool runSuccess = false;
    bool timeout = false;

    long long executionTimeMs = 0;
    std::size_t peakMemoryKB = 0;

    double semanticScore = 0.0;
    double passRate = 0.0;
    double timeScore = 0.0;
    double memoryScore = 0.0;

    std::string compileLog;
};

std::vector<std::string> findCandidateFiles(const std::string& candidateDir);
bool runCommandWithHiddenWindow(const std::string& command, std::string& logOutput, DWORD timeoutMs);
bool compileCandidate(const std::string& sourcePath, const std::string& exePath, std::string& compileLog);
CandidateResult runExecutableAndMeasure(const std::string& exePath, CandidateResult result, DWORD timeoutMs);
double calculateTimeScore(long long timeMs);
double calculateMemoryScore(std::size_t memoryKB);
CandidateResult evaluateCandidate(const std::string& sourcePath);
void writeCsvResult(const std::vector<CandidateResult>& results, const std::string& outputPath);

#endif
