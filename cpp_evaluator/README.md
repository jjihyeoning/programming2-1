# C++ 실행 평가 모듈

## 1. 담당 범위

이 폴더는 프로젝트의 3단계인 C++ 실행 평가 모듈을 담당한다.

3단계의 목적은 여러 LLM이 생성한 C++ 후보 코드가 실제로 컴파일되고 실행 가능한지 확인하고, 실행 성능을 측정하여 최종 점수 계산에 필요한 `time_score`와 `memory_score`를 생성하는 것이다.

현재 이 모듈은 최종 점수인 `FinalScore`를 계산하지 않는다.  
`FinalScore` 계산은 4단계에서 수행한다.

---

## 2. 현재 구현한 기능

현재 `evaluator.cpp`에서 구현한 기능은 다음과 같다.

### 후보 코드 자동 탐색

`candidates` 폴더 안에 있는 `.cpp` 파일들을 자동으로 탐색한다.

예시 구조:

```txt
cpp_evaluator/
├── evaluator.cpp
├── candidates/
│   ├── code_gpt.cpp
│   ├── code_claude.cpp
│   └── code_gemini.cpp
└── results/
```

### 후보 코드 컴파일

각 후보 코드를 `g++`로 컴파일한다.

```txt
g++ "candidates/code_gpt.cpp" -o "build/code_gpt.exe" -std=c++17
```

컴파일에 성공하면 `build` 폴더 안에 실행 파일이 생성된다.  
컴파일에 실패한 후보 코드는 실행하지 않고 `time_score`, `memory_score`를 `0.00`으로 처리한다.

### 후보 코드 실행

컴파일에 성공한 실행 파일을 C++ 코드 내부에서 직접 실행한다.

실행에는 Windows API의 `CreateProcessA()`를 사용한다.

현재 측정하는 항목은 다음과 같다.

```txt
- 실행 성공 여부
- 시간 초과 여부
- 실행 시간
- 최대 메모리 사용량
```

실행 제한 시간은 5초이다.

```txt
timeoutMs = 5000
```

5초를 넘으면 시간 초과로 판단하고 프로세스를 강제 종료한다.

### 실행 시간 측정

실행 시간은 C++ `chrono` 라이브러리를 사용하여 ms 단위로 측정한다.

예시:

```txt
executionTimeMs = 120
```

이 값은 `time_score` 계산에 사용된다.

### 메모리 사용량 측정

메모리 사용량은 Windows API의 `GetProcessMemoryInfo()`를 사용하여 측정한다.

후보 코드가 실행 중 사용한 최대 메모리 사용량을 KB 단위로 저장한다.

예시:

```txt
peakMemoryKB = 3500
```

이 값은 `memory_score` 계산에 사용된다.

---

## 3. 점수 계산 기준

### time_score

실행 시간이 짧을수록 높은 점수를 부여한다.

```txt
10ms 이하    → 1.00
50ms 이하    → 0.90
100ms 이하   → 0.80
300ms 이하   → 0.60
700ms 이하   → 0.40
1000ms 이하  → 0.20
1000ms 초과  → 0.00
```

### memory_score

메모리 사용량이 적을수록 높은 점수를 부여한다.

```txt
1MB 이하    → 1.00
4MB 이하    → 0.90
8MB 이하    → 0.80
16MB 이하   → 0.60
32MB 이하   → 0.40
64MB 이하   → 0.20
64MB 초과   → 0.00
```

---

## 4. CSV 출력 형식

평가 결과는 다음 경로에 저장된다.

```txt
results/execution_metrics.csv
```

현재 CSV 출력 형식은 다음과 같다.

```csv
file_name,semantic_score,pass_rate,time_score,memory_score
code_gpt.cpp,0.00,0.00,0.60,0.90
code_claude.cpp,0.00,0.00,0.80,0.80
code_gemini.cpp,0.00,0.00,0.00,0.00
```

현재 3단계 C++ 모듈에서 실제로 계산하는 값은 다음 두 가지이다.

```txt
time_score
memory_score
```

`semantic_score`와 `pass_rate`는 현재 단계에서 계산하지 않기 때문에 `0.00`의 placeholder 값으로 저장한다.

---

## 5. 현재 구현하지 않은 기능

현재 `evaluator.cpp`에서는 다음 기능을 구현하지 않았다.

```txt
- semantic_score 계산
- pass_rate 계산
- FinalScore 계산
- 최종 후보 선택
- 테스트케이스 기반 정답 검증
```

각 항목의 담당 단계는 다음과 같다.

```txt
semantic_score → 2단계 Python AI 평가에서 계산
pass_rate      → 테스트케이스 기반 정답 검증 단계에서 계산
FinalScore     → 4단계 최종 점수 계산 단계에서 계산
최종 후보 선택 → 4단계에서 수행
```

---

## 6. 실행 방법

PowerShell에서 `cpp_evaluator` 폴더로 이동한 뒤 컴파일한다.

```powershell
g++ evaluator.cpp -o evaluator.exe -std=c++17 -lpsapi
```

실행한다.

```powershell
.\evaluator.exe
```

실행 후 결과는 다음 파일에서 확인할 수 있다.

```txt
results/execution_metrics.csv
```

---

## 7. 핵심 함수 정리

### findCandidateFiles()

`candidates` 폴더에서 `.cpp` 후보 코드 파일을 찾는 함수이다.

### compileCandidate()

후보 C++ 코드를 `g++`로 컴파일하는 함수이다.

### runCommandWithHiddenWindow()

외부 명령어를 실행하는 함수이다.  
현재는 컴파일 명령어 실행에 사용된다.

### runExecutableAndMeasure()

컴파일된 실행 파일을 실행하고 실행 시간과 메모리 사용량을 측정하는 함수이다.

### calculateTimeScore()

실행 시간을 기준으로 `time_score`를 계산하는 함수이다.

### calculateMemoryScore()

메모리 사용량을 기준으로 `memory_score`를 계산하는 함수이다.

### evaluateCandidate()

후보 코드 하나를 전체 평가하는 함수이다.

### writeCsvResult()

평가 결과를 CSV 파일로 저장하는 함수이다.

---

## 8. 앞으로 해야 할 일

최종 프로젝트에서는 다음 기능을 추가하거나 다른 단계와 연결해야 한다.

```txt
1. 테스트케이스 기반 pass_rate 계산 기능 추가
2. 2단계 Python AI 평가에서 생성한 semantic_score와 연결
3. 4단계 FinalScore 계산 모듈과 연결
4. 필요하면 evaluator.cpp를 기능별 파일로 분리
```

최종 점수 계산 공식은 다음과 같다.

```txt
FinalScore =
semantic_score × 0.3
+ pass_rate × 0.4
+ time_score × 0.2
+ memory_score × 0.1
```

현재 C++ 모듈은 이 중 `time_score`와 `memory_score`를 제공한다.

---

## 9. 주의사항

현재 코드는 Windows 환경 기준으로 작성되었다.

사용 중인 Windows API는 다음과 같다.

```txt
CreateProcessA
WaitForSingleObject
TerminateProcess
GetExitCodeProcess
GetProcessMemoryInfo
```

Linux 또는 macOS에서 실행하려면 프로세스 실행 및 메모리 측정 부분을 수정해야 한다.

또한 후보 코드를 컴파일하기 위해 `g++`가 설치되어 있어야 한다.

```powershell
g++ --version
```

---

## 10. GitHub에 올리지 않는 것을 권장하는 파일

다음 파일과 폴더는 실행 결과물이므로 GitHub에 올리지 않는 것을 권장한다.

```txt
build/
results/
*.exe
*.o
compile_temp_log.txt
```

`.gitignore`에 추가할 수 있는 예시는 다음과 같다.

```gitignore
cpp_evaluator/build/
cpp_evaluator/results/
cpp_evaluator/*.exe
*.exe
*.o
compile_temp_log.txt
```

---

## 11. 현재 단계 요약

현재 구현 완료:

```txt
- candidates 폴더에서 후보 코드 탐색
- g++ 컴파일
- 실행 파일 실행
- 실행 시간 측정
- 메모리 사용량 측정
- time_score 계산
- memory_score 계산
- execution_metrics.csv 저장
```

현재 미구현:

```txt
- semantic_score 계산
- pass_rate 계산
- FinalScore 계산
- 최종 후보 선택
- 테스트케이스 기반 정답 검증
```

한 줄 요약:

```txt
이 모듈은 LLM이 생성한 C++ 후보 코드를 실제로 컴파일하고 실행하여, 최종 점수 계산에 필요한 time_score와 memory_score를 생성하는 3단계 실행 평가 모듈이다.
```
