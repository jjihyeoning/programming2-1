import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sparkles,
  Code2,
  Copy,
  Check,
  Cpu,
  Timer,
  MemoryStick,
  ArrowRight,
  RotateCcw,
  Trophy,
  Loader2,
} from "lucide-react";
import { toast, Toaster } from "sonner";

export const Route = createFileRoute("/")({
  component: Index,
  head: () => ({
    meta: [
      { title: "LLLLMM - 다중 LLM 코드 교차 검증" },
      {
        name: "description",
        content: "백엔드에서 LLM 후보 코드를 생성하고 C++ evaluator와 finalscore로 평가합니다.",
      },
    ],
  }),
});

type Stage = "input" | "candidates" | "scoring" | "result" | "final";

type CandidateCode = {
  model: string;
  code: string;
};

type EvaluationResult = {
  rank: number;
  fileName: string;
  semanticScore: number;
  passRate: number;
  timeScore: number;
  memoryScore: number;
  finalScore: number;
};

type ExecutionMetric = {
  runtimeMs: number;
  memoryKb: number;
};

type EvaluatedCandidate = {
  id: string;
  model: string;
  color: string;
  code: string;
  scores: {
    correctness: number;
    style: number;
    performance: number;
    crossReview: number;
  };
  total: number;
  runtimeMs: number;
  memoryKb: number;
};

const LANGUAGES = ["Python", "C", "C++", "Java"];
const MODEL_COLORS = ["oklch(0.78 0.12 250)", "oklch(0.8 0.11 35)", "oklch(0.78 0.11 160)"];

function Index() {
  const [stage, setStage] = useState<Stage>("input");
  const [problem, setProblem] = useState("");
  const [language, setLanguage] = useState("C++");
  const [candidates, setCandidates] = useState<CandidateCode[]>([]);
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [executionMetrics, setExecutionMetrics] = useState<Record<string, ExecutionMetric>>({});
  const [copied, setCopied] = useState(false);
  const evaluatedCandidates = buildEvaluatedCandidates(candidates, results, executionMetrics);

  const winner = evaluatedCandidates.length
    ? [...evaluatedCandidates].sort((a, b) => b.total - a.total)[0]
    : null;

  const handleSubmit = async () => {
    if (!problem.trim()) {
      toast.error("문제 내용을 입력해주세요.");
      return;
    }

    await requestBackendEvaluation("input");
  };

  const runScoring = async () => {
    if (candidates.length === 0) {
      toast.error("평가할 후보 코드가 없습니다.");
      return;
    }

    await requestBackendEvaluation("candidates");
  };

  const requestBackendEvaluation = async (fallbackStage: Stage) => {
    try {
      setStage("scoring");

      const response = await fetch("http://127.0.0.1:5000/api/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json; charset=utf-8",
        },
        body: JSON.stringify({
          problem,
          language,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.message || "백엔드 평가 실패");
      }

      setCandidates(data.candidates || []);
      setResults(data.results || []);
      setExecutionMetrics(data.executionMetrics || {});
      setStage("result");
      toast.success("백엔드 평가가 완료되었습니다.");
    } catch (error) {
      console.error(error);
      toast.error("백엔드 요청 중 오류가 발생했습니다.");
      setStage(fallbackStage);
    }
  };

  const reset = () => {
    setStage("input");
    setProblem("");
    setCandidates([]);
    setResults([]);
    setExecutionMetrics({});
  };

  const copyCode = async () => {
    if (!winner) return;

    await navigator.clipboard.writeText(winner.code);
    setCopied(true);
    toast.success("코드가 복사되었습니다.");
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="min-h-screen bg-background">
      <Toaster position="top-center" richColors />

      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl text-primary-foreground"
            style={{ background: "var(--gradient-primary)" }}
          >
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">LLLLMM</h1>
            <p className="text-xs text-muted-foreground">다중 LLM 코드 교차 검증</p>
          </div>
        </div>

        <StageIndicator stage={stage} />
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-20">
        {stage === "input" && (
          <InputStage
            problem={problem}
            setProblem={setProblem}
            language={language}
            setLanguage={setLanguage}
            onSubmit={handleSubmit}
          />
        )}

        {stage === "candidates" && (
          <CandidatesStage
            candidates={candidates}
            language={language}
            onNext={runScoring}
            onBack={reset}
          />
        )}

        {stage === "scoring" && <ScoringStage />}

        {stage === "result" && winner && (
          <ResultStage
            candidates={candidates}
            evaluatedCandidates={evaluatedCandidates}
            onReset={reset}
            onShowFinal={() => setStage("final")}
          />
        )}

        {stage === "final" && winner && (
          <FinalStage
            winner={winner}
            language={language}
            onBack={() => setStage("result")}
            onReset={reset}
            onCopy={copyCode}
            copied={copied}
          />
        )}
      </main>
    </div>
  );
}

function StageIndicator({ stage }: { stage: Stage }) {
  const steps: { id: Stage; label: string }[] = [
    { id: "input", label: "입력" },
    { id: "candidates", label: "후보" },
    { id: "scoring", label: "검증" },
    { id: "result", label: "결과" },
    { id: "final", label: "추천" },
  ];

  const idx = steps.findIndex((s) => s.id === stage);

  return (
    <div className="hidden items-center gap-2 md:flex">
      {steps.map((s, i) => (
        <div key={s.id} className="flex items-center gap-2">
          <div
            className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-colors ${
              i <= idx
                ? "text-primary-foreground"
                : "border border-border bg-card text-muted-foreground"
            }`}
            style={i <= idx ? { background: "var(--gradient-primary)" } : undefined}
          >
            {i + 1}
          </div>

          <span
            className={`text-sm ${
              i === idx ? "font-medium text-foreground" : "text-muted-foreground"
            }`}
          >
            {s.label}
          </span>

          {i < steps.length - 1 && <div className="mx-1 h-px w-6 bg-border" />}
        </div>
      ))}
    </div>
  );
}

function InputStage({
  problem,
  setProblem,
  language,
  setLanguage,
  onSubmit,
}: {
  problem: string;
  setProblem: (v: string) => void;
  language: string;
  setLanguage: (v: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="mx-auto max-w-3xl pt-8">
      <div className="mb-8 text-center">
        <h2 className="text-4xl font-extrabold tracking-tight text-foreground md:text-5xl">
          다중 LLM 코드 평가
          <br />
          <span
            className="bg-clip-text text-transparent"
            style={{ backgroundImage: "var(--gradient-primary)" }}
          >
            LLLLMM
          </span>
        </h2>

        <p className="mt-4 text-base font-medium text-muted-foreground">
          백엔드에서 LLM 후보 코드를 생성하고 C++ evaluator와 finalscore로 평가합니다.
        </p>
      </div>

      <Card
        className="rounded-2xl border-border/60 p-6 backdrop-blur"
        style={{ boxShadow: "var(--shadow-soft)" }}
      >
        <label className="mb-2 block text-sm font-semibold text-foreground">
          문제를 입력하세요
        </label>

        <Textarea
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          className="min-h-[140px] resize-none rounded-xl border-border bg-background/60 text-base"
        />

        <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="sm:w-56">
            <label className="mb-2 block text-sm font-semibold text-foreground">언어</label>

            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="rounded-xl bg-background/60">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGES.map((l) => (
                  <SelectItem key={l} value={l}>
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button
            size="lg"
            onClick={onSubmit}
            className="rounded-xl text-primary-foreground"
            style={{
              background: "var(--gradient-primary)",
              boxShadow: "var(--shadow-card)",
            }}
          >
            입력 완료
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </Card>

      <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          { icon: Code2, t: "후보 생성", d: "백엔드 LLM 호출" },
          { icon: Cpu, t: "성능 측정", d: "C++ evaluator 실행" },
          { icon: Trophy, t: "최종 점수", d: "finalscore 계산" },
        ].map((f) => (
          <div
            key={f.t}
            className="rounded-xl border border-border/60 bg-card/60 p-4 backdrop-blur"
          >
            <f.icon className="h-5 w-5 text-primary" />
            <p className="mt-2 text-sm font-medium text-foreground">{f.t}</p>
            <p className="text-xs text-muted-foreground">{f.d}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CandidatesStage({
  candidates,
  language,
  onNext,
  onBack,
}: {
  candidates: CandidateCode[];
  language: string;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <div className="pt-4">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">후보 목록</h2>
          <p className="text-sm text-muted-foreground">
            {candidates.length}개의 LLM이 {language} 코드를 생성했습니다.
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="ghost" onClick={onBack} className="rounded-xl">
            <RotateCcw className="mr-1 h-4 w-4" />
            다시 입력
          </Button>

          <Button
            onClick={onNext}
            className="rounded-xl text-primary-foreground"
            style={{ background: "var(--gradient-primary)" }}
          >
            교차 검증 시작
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {candidates.map((c, index) => (
          <Card
            key={`${c.model}-${index}`}
            className="overflow-hidden rounded-2xl border-border/60"
            style={{ boxShadow: "var(--shadow-card)" }}
          >
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{
                    background: MODEL_COLORS[index % MODEL_COLORS.length],
                  }}
                />
                <span className="text-sm font-semibold text-foreground">{c.model}</span>
              </div>

              <Badge variant="secondary" className="rounded-full text-xs">
                {language}
              </Badge>
            </div>

            <pre className="max-h-72 overflow-auto bg-muted/40 p-4 text-xs leading-relaxed text-foreground">
              <code>{c.code}</code>
            </pre>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ScoringStage() {
  const steps = [
    "LLM 간 교차 검증 진행 중..",
    "C++ 성능 측정 진행 중..",
    "가중치 기반 최종 점수 계산 중..",
  ];

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center">
      <div
        className="flex h-16 w-16 items-center justify-center rounded-2xl text-primary-foreground"
        style={{
          background: "var(--gradient-primary)",
          boxShadow: "var(--shadow-soft)",
        }}
      >
        <Loader2 className="h-7 w-7 animate-spin" />
      </div>

      <h2 className="mt-6 text-2xl font-bold text-foreground">코드 생성, 평가 중</h2>

      <ul className="mt-4 space-y-1.5 text-center text-sm text-muted-foreground">
        {steps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </div>
  );
}

function ResultStage({
  candidates,
  evaluatedCandidates,
  onReset,
  onShowFinal,
}: {
  candidates: CandidateCode[];
  evaluatedCandidates: EvaluatedCandidate[];
  onReset: () => void;
  onShowFinal: () => void;
}) {
  const sorted = [...evaluatedCandidates].sort((a, b) => b.total - a.total);

  return (
    <div className="pt-4">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-foreground">검증 결과</h2>
          <p className="text-sm font-medium text-muted-foreground">
            가중치: 정확성 35% · 성능 30% · 교차검증 25% · 속도 10%
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="ghost" onClick={onReset} className="rounded-xl">
            <RotateCcw className="mr-1 h-4 w-4" />새 문제
          </Button>

          <Button
            onClick={onShowFinal}
            className="rounded-xl text-primary-foreground font-semibold"
            style={{ background: "var(--gradient-primary)" }}
          >
            최선 후보 코드 보기
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      {candidates.length > 0 && (
        <section className="mb-8">
          <div className="mb-3">
            <h2 className="text-xl font-extrabold text-foreground">Candidate Codes</h2>
            <p className="text-sm font-medium text-muted-foreground">
              평가를 통과한 후보 코드입니다.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {candidates.map((candidate, index) => (
              <Card
                key={`${candidate.model}-${index}`}
                className="overflow-hidden rounded-2xl border-border/60"
                style={{ boxShadow: "var(--shadow-card)" }}
              >
                <div className="flex items-center gap-2 border-b border-border/60 px-4 py-3">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{
                      background: MODEL_COLORS[index % MODEL_COLORS.length],
                    }}
                  />
                  <h3 className="text-sm font-semibold text-foreground">{candidate.model}</h3>
                </div>

                <pre className="max-h-72 overflow-auto bg-muted/40 p-4 text-xs leading-relaxed text-foreground">
                  <code>{candidate.code}</code>
                </pre>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-3">
          <h2 className="text-xl font-extrabold text-foreground">Evaluation Results</h2>
          <p className="text-sm font-medium text-muted-foreground">
            C++ 실행 평가와 finalscore 계산 결과입니다.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {sorted.map((c, i) => (
            <Card
              key={c.id}
              className={`rounded-2xl p-5 transition ${
                i === 0 ? "border-primary/40 ring-2 ring-primary/20" : "border-border/60"
              }`}
              style={{
                boxShadow: i === 0 ? "var(--shadow-soft)" : "var(--shadow-card)",
              }}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />

                  <span className="font-bold text-foreground">{c.model}</span>

                  {i === 0 && (
                    <Badge
                      className="rounded-full text-primary-foreground font-semibold"
                      style={{ background: "var(--gradient-primary)" }}
                    >
                      <Trophy className="mr-1 h-3 w-3" />
                      BEST
                    </Badge>
                  )}
                </div>

                <div className="text-right">
                  <div className="text-2xl font-extrabold text-foreground">{c.total}</div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Score
                  </div>
                </div>
              </div>

              <div className="space-y-2.5">
                <ScoreBar label="정확성" value={c.scores.correctness} />
                <ScoreBar label="성능 (C++ 측정)" value={c.scores.performance} />
                <ScoreBar label="메모리" value={c.scores.crossReview} />
                <ScoreBar label="의미 유사도" value={c.scores.style} />
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

function FinalStage({
  winner,
  language,
  onBack,
  onReset,
  onCopy,
  copied,
}: {
  winner: EvaluatedCandidate;
  language: string;
  onBack: () => void;
  onReset: () => void;
  onCopy: () => void;
  copied: boolean;
}) {
  return (
    <div className="pt-4">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-foreground">최선 후보 코드</h2>
          <p className="text-sm font-medium text-muted-foreground">
            교차 검증 및 성능 측정을 거쳐 최적의 코드입니다.
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="ghost" onClick={onBack} className="rounded-xl">
            검증 결과로
          </Button>

          <Button variant="ghost" onClick={onReset} className="rounded-xl">
            <RotateCcw className="mr-1 h-4 w-4" />새 문제
          </Button>
        </div>
      </div>

      <Card
        className="overflow-hidden rounded-2xl border-primary/40"
        style={{ boxShadow: "var(--shadow-soft)" }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 bg-card/80 px-5 py-4">
          <div className="flex items-center gap-3">
            <div
              className="flex h-9 w-9 items-center justify-center rounded-lg text-primary-foreground"
              style={{ background: "var(--gradient-primary)" }}
            >
              <Trophy className="h-5 w-5" />
            </div>

            <div>
              <div className="text-sm font-bold text-foreground">{winner.model}</div>
              <div className="text-xs font-medium text-muted-foreground">
                {language} · 최종 점수 {winner.total}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Metric icon={Timer} label="실행 시간" value={`${winner.runtimeMs} ms`} />
            <Metric icon={MemoryStick} label="메모리" value={`${winner.memoryKb} KB`} />

            <Button
              onClick={onCopy}
              className="rounded-xl text-primary-foreground font-semibold"
              style={{ background: "var(--gradient-primary)" }}
            >
              {copied ? (
                <>
                  <Check className="mr-1 h-4 w-4" /> 복사됨
                </>
              ) : (
                <>
                  <Copy className="mr-1 h-4 w-4" /> 코드 복사
                </>
              )}
            </Button>
          </div>
        </div>

        <pre className="max-h-[420px] overflow-auto bg-muted/40 p-5 text-sm leading-relaxed text-foreground">
          <code>{winner.code}</code>
        </pre>
      </Card>
    </div>
  );
}

function buildEvaluatedCandidates(
  candidates: CandidateCode[],
  results: EvaluationResult[],
  executionMetrics: Record<string, ExecutionMetric>,
): EvaluatedCandidate[] {
  const resultByFileName = new Map(results.map((result) => [result.fileName, result]));

  return candidates.map((candidate, index) => {
    const fileName = makeCandidateFileName(candidate.model, index + 1);
    const result = resultByFileName.get(fileName) || results[index];
    const metrics = executionMetrics[fileName] || {
      runtimeMs: 0,
      memoryKb: 0,
    };

    return {
      id: `${candidate.model}-${index}`,
      model: candidate.model,
      color: MODEL_COLORS[index % MODEL_COLORS.length],
      code: candidate.code,
      scores: {
        correctness: normalizeScore(result?.passRate),
        style: normalizeScore(result?.semanticScore),
        performance: normalizeScore(result?.timeScore),
        crossReview: normalizeScore(result?.memoryScore),
      },
      total: normalizeScore(result?.finalScore),
      runtimeMs: metrics.runtimeMs,
      memoryKb: metrics.memoryKb,
    };
  });
}

function makeCandidateFileName(model: string, index: number) {
  const safeModelName = model.trim().replace(/[\s/\\:*?"<>|]/g, "_");
  return `code_${safeModelName || `model_${index}`}.cpp`;
}

function normalizeScore(value?: number) {
  const parsed = Number(value || 0);
  const normalized = parsed >= 0 && parsed <= 1 ? parsed * 100 : parsed;
  return Number(normalized.toFixed(1));
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-muted-foreground">{label}</span>
        <span className="font-bold text-foreground">{value}</span>
      </div>

      <Progress value={value} className="h-1.5" />
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Timer;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-border/60 bg-background/60 px-3 py-2">
      <Icon className="h-4 w-4 text-primary" />
      <div className="leading-tight">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className="text-sm font-semibold text-foreground">{value}</div>
      </div>
    </div>
  );
}
