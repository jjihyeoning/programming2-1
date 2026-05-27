#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;

struct Candidate {
    string file_name;
    double semantic_score = 0.0;
    double pass_rate = 0.0;
    double time_score = 0.0;
    double memory_score = 0.0;
    double final_score = 0.0;
};

const double WEIGHT_SEMANTIC = 0.3;
const double WEIGHT_PASS = 0.4;
const double WEIGHT_TIME = 0.2;
const double WEIGHT_MEMORY = 0.1;

vector<string> splitCSVLine(const string& line) {
    vector<string> result;
    string token;
    stringstream ss(line);

    while (getline(ss, token, ',')) {
        result.push_back(token);
    }

    return result;
}

bool isValidScore(double score) {
    return score >= 0.0 && score <= 1.0;
}

double parseScore(const string& value, double fallback = 0.0) {
    try {
        return stod(value);
    }
    catch (...) {
        return fallback;
    }
}

unordered_map<string, double> readSemanticCSV(const string& filename) {
    unordered_map<string, double> semanticMap;
    ifstream file(filename);

    if (!file.is_open()) {
        cerr << "[ERROR] semantic_result.csv file not found: " << filename << '\n';
        return semanticMap;
    }

    string line;
    getline(file, line);

    while (getline(file, line)) {
        vector<string> cols = splitCSVLine(line);
        if (cols.size() < 2) {
            continue;
        }

        double semantic_score = parseScore(cols[1], -1.0);
        if (!isValidScore(semantic_score)) {
            cerr << "[WARN] Invalid semantic_score for " << cols[0] << ": " << cols[1] << '\n';
            continue;
        }

        semanticMap[cols[0]] = semantic_score;
    }

    return semanticMap;
}

double calculateFinalScore(const Candidate& c) {
    return c.semantic_score * WEIGHT_SEMANTIC
        + c.pass_rate * WEIGHT_PASS
        + c.time_score * WEIGHT_TIME
        + c.memory_score * WEIGHT_MEMORY;
}

vector<Candidate> readExecutionCSV(
    const string& filename,
    const unordered_map<string, double>& semanticMap
) {
    vector<Candidate> candidates;
    ifstream file(filename);

    if (!file.is_open()) {
        cerr << "[ERROR] execution_result.csv file not found: " << filename << '\n';
        return candidates;
    }

    string line;
    getline(file, line);

    while (getline(file, line)) {
        vector<string> cols = splitCSVLine(line);
        if (cols.size() < 5) {
            cerr << "[WARN] Invalid execution_result.csv row skipped: " << line << '\n';
            continue;
        }

        Candidate c;
        c.file_name = cols[0];

        auto semanticIt = semanticMap.find(c.file_name);
        if (semanticIt == semanticMap.end()) {
            cerr << "[WARN] semantic_result.csv has no matching file_name for "
                 << c.file_name << "; skipped.\n";
            continue;
        }

        c.semantic_score = semanticIt->second;
        c.pass_rate = parseScore(cols[2], -1.0);
        c.time_score = parseScore(cols[3], -1.0);
        c.memory_score = parseScore(cols[4], -1.0);

        if (!isValidScore(c.pass_rate) ||
            !isValidScore(c.time_score) ||
            !isValidScore(c.memory_score)) {
            cerr << "[WARN] Invalid execution score for " << c.file_name << "; skipped.\n";
            continue;
        }

        c.final_score = calculateFinalScore(c);
        candidates.push_back(c);
    }

    return candidates;
}

void sortCandidatesByFinalScore(vector<Candidate>& candidates) {
    sort(candidates.begin(), candidates.end(), [](const Candidate& a, const Candidate& b) {
        return a.final_score > b.final_score;
    });
}

bool writeFinalScoreCSV(const string& filename, const vector<Candidate>& candidates) {
    ofstream file(filename);

    if (!file.is_open()) {
        cerr << "[ERROR] Could not create final_scores.csv: " << filename << '\n';
        return false;
    }

    file << "rank,file_name,semantic_score,pass_rate,time_score,memory_score,final_score\n";
    file << fixed << setprecision(4);

    for (size_t i = 0; i < candidates.size(); ++i) {
        const Candidate& c = candidates[i];
        file << i + 1 << ","
             << c.file_name << ","
             << c.semantic_score << ","
             << c.pass_rate << ","
             << c.time_score << ","
             << c.memory_score << ","
             << c.final_score << "\n";
    }

    return true;
}

int main() {
    const string semanticFile = "semantic_result.csv";
    const string executionFile = "execution_result.csv";
    const string outputFile = "final_scores.csv";

    unordered_map<string, double> semanticMap = readSemanticCSV(semanticFile);
    vector<Candidate> candidates = readExecutionCSV(executionFile, semanticMap);

    if (candidates.empty()) {
        cerr << "[ERROR] No candidates available for final scoring.\n";
        return 1;
    }

    sortCandidatesByFinalScore(candidates);

    cout << fixed << setprecision(4);
    cout << "\n===== Final Score Results =====\n";
    for (size_t i = 0; i < candidates.size(); ++i) {
        const Candidate& c = candidates[i];
        cout << i + 1 << " | "
             << c.file_name
             << " | final_score: " << c.final_score
             << " | semantic: " << c.semantic_score
             << " | pass: " << c.pass_rate
             << " | time: " << c.time_score
             << " | memory: " << c.memory_score
             << '\n';
    }

    if (!writeFinalScoreCSV(outputFile, candidates)) {
        return 1;
    }

    cout << "[INFO] final_scores.csv saved: " << outputFile << '\n';
    return 0;
}
