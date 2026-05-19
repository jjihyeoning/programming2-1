#include "InputManager.h"

#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;
namespace fs = std::filesystem;

struct Submission {
    string model;
    string code;
};

class RequestJsonParser {
public:
    explicit RequestJsonParser(const string& jsonText) : text(jsonText) {}

    vector<Submission> parseSubmissions() {
        size_t submissionsKey = text.find("\"submissions\"");
        if (submissionsKey == string::npos) {
            throw runtime_error("request_body.json에 submissions 배열이 없습니다.");
        }

        size_t colon = text.find(':', submissionsKey);
        if (colon == string::npos) {
            throw runtime_error("submissions 형식이 올바르지 않습니다.");
        }

        pos = colon + 1;
        skipWhitespace();
        expect('[');

        vector<Submission> submissions;

        while (true) {
            skipWhitespace();
            if (peek() == ']') {
                ++pos;
                break;
            }

            submissions.push_back(parseSubmissionObject());

            skipWhitespace();
            if (peek() == ',') {
                ++pos;
                continue;
            }
            if (peek() == ']') {
                ++pos;
                break;
            }

            throw runtime_error("submissions 배열 형식이 올바르지 않습니다.");
        }

        return submissions;
    }

private:
    const string& text;
    size_t pos = 0;

    char peek() const {
        return pos < text.size() ? text[pos] : '\0';
    }

    void skipWhitespace() {
        while (pos < text.size() && isspace(static_cast<unsigned char>(text[pos]))) {
            ++pos;
        }
    }

    void expect(char expected) {
        if (peek() != expected) {
            throw runtime_error("JSON 형식이 올바르지 않습니다.");
        }
        ++pos;
    }

    string parseString() {
        expect('"');
        string result;

        while (pos < text.size()) {
            char ch = text[pos++];

            if (ch == '"') {
                return result;
            }

            if (ch != '\\') {
                result += ch;
                continue;
            }

            if (pos >= text.size()) {
                throw runtime_error("문자열 escape 형식이 올바르지 않습니다.");
            }

            char escaped = text[pos++];
            switch (escaped) {
            case '"': result += '"'; break;
            case '\\': result += '\\'; break;
            case '/': result += '/'; break;
            case 'b': result += '\b'; break;
            case 'f': result += '\f'; break;
            case 'n': result += '\n'; break;
            case 'r': result += '\r'; break;
            case 't': result += '\t'; break;
            case 'u':
                appendUnicodeEscapeAsUtf8(result);
                break;
            default:
                result += escaped;
                break;
            }
        }

        throw runtime_error("문자열이 닫히지 않았습니다.");
    }

    void appendUnicodeEscapeAsUtf8(string& output) {
        if (pos + 4 > text.size()) {
            throw runtime_error("Unicode escape 형식이 올바르지 않습니다.");
        }

        int codepoint = 0;
        for (int i = 0; i < 4; ++i) {
            char ch = text[pos++];
            codepoint <<= 4;

            if (ch >= '0' && ch <= '9') codepoint += ch - '0';
            else if (ch >= 'a' && ch <= 'f') codepoint += ch - 'a' + 10;
            else if (ch >= 'A' && ch <= 'F') codepoint += ch - 'A' + 10;
            else throw runtime_error("Unicode escape 형식이 올바르지 않습니다.");
        }

        if (codepoint <= 0x7F) {
            output += static_cast<char>(codepoint);
        }
        else if (codepoint <= 0x7FF) {
            output += static_cast<char>(0xC0 | (codepoint >> 6));
            output += static_cast<char>(0x80 | (codepoint & 0x3F));
        }
        else {
            output += static_cast<char>(0xE0 | (codepoint >> 12));
            output += static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F));
            output += static_cast<char>(0x80 | (codepoint & 0x3F));
        }
    }

    void skipValue() {
        skipWhitespace();

        if (peek() == '"') {
            parseString();
            return;
        }

        if (peek() == '{') {
            ++pos;
            int depth = 1;
            while (pos < text.size() && depth > 0) {
                if (peek() == '"') parseString();
                else if (peek() == '{') { ++depth; ++pos; }
                else if (peek() == '}') { --depth; ++pos; }
                else ++pos;
            }
            return;
        }

        if (peek() == '[') {
            ++pos;
            int depth = 1;
            while (pos < text.size() && depth > 0) {
                if (peek() == '"') parseString();
                else if (peek() == '[') { ++depth; ++pos; }
                else if (peek() == ']') { --depth; ++pos; }
                else ++pos;
            }
            return;
        }

        while (pos < text.size() && peek() != ',' && peek() != '}' && peek() != ']') {
            ++pos;
        }
    }

    Submission parseSubmissionObject() {
        Submission submission;

        expect('{');
        while (true) {
            skipWhitespace();
            if (peek() == '}') {
                ++pos;
                break;
            }

            string key = parseString();
            skipWhitespace();
            expect(':');
            skipWhitespace();

            if (key == "model" && peek() == '"') {
                submission.model = parseString();
            }
            else if (key == "code" && peek() == '"') {
                submission.code = parseString();
            }
            else {
                skipValue();
            }

            skipWhitespace();
            if (peek() == ',') {
                ++pos;
                continue;
            }
            if (peek() == '}') {
                ++pos;
                break;
            }

            throw runtime_error("submission 객체 형식이 올바르지 않습니다.");
        }

        return submission;
    }
};

bool isBlank(const string& value) {
    for (char ch : value) {
        if (!isspace(static_cast<unsigned char>(ch))) {
            return false;
        }
    }
    return true;
}

string makeSafeFileName(string name) {
    if (isBlank(name)) {
        return "";
    }

    for (char& ch : name) {
        unsigned char uch = static_cast<unsigned char>(ch);
        if (isspace(uch) || ch == '/' || ch == '\\' || ch == ':' || ch == '*' ||
            ch == '?' || ch == '"' || ch == '<' || ch == '>' || ch == '|') {
            ch = '_';
        }
    }

    return name;
}

void prepareCandidatesFromRequestJson() {
    const fs::path requestPath = "request_body.json";
    const fs::path candidatesDir = "candidates";

    ifstream fin(requestPath, ios::binary);
    if (!fin.is_open()) {
        throw runtime_error("request_body.json 파일을 열 수 없습니다.");
    }

    string jsonText((istreambuf_iterator<char>(fin)), istreambuf_iterator<char>());
    fin.close();

    RequestJsonParser parser(jsonText);
    vector<Submission> submissions = parser.parseSubmissions();

    if (fs::exists(candidatesDir)) {
        fs::remove_all(candidatesDir);
    }
    fs::create_directories(candidatesDir);

    int savedCount = 0;
    int fallbackIndex = 1;

    for (const Submission& submission : submissions) {
        if (isBlank(submission.code)) {
            continue;
        }

        string safeModelName = makeSafeFileName(submission.model);
        if (safeModelName.empty()) {
            safeModelName = "model_" + to_string(fallbackIndex);
        }
        ++fallbackIndex;

        fs::path outputPath = candidatesDir / ("code_" + safeModelName + ".cpp");
        ofstream fout(outputPath, ios::binary);
        if (!fout.is_open()) {
            throw runtime_error("후보 코드 파일을 생성할 수 없습니다: " + outputPath.string());
        }

        fout << submission.code;
        fout.close();
        ++savedCount;
    }

    if (savedCount == 0) {
        throw runtime_error("저장할 후보 코드가 없습니다.");
    }

    cout << "[INFO] request_body.json에서 후보 코드 " << savedCount << "개를 저장했습니다." << endl;
}
