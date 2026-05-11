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
      { title: "MultiVerify · 다중 LLM 코드 교차 검증" },
      {
        name: "description",
        content: "여러 LLM의 코드 응답을 교차 검증하고 성능을 측정해 최적의 코드를 추천합니다.",
      },
    ],
  }),
});

type Stage = "input" | "candidates" | "scoring" | "result" | "final";

type Candidate = {
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

const LANGUAGES = ["Python", "JavaScript", "TypeScript", "C++", "Java", "Go", "Rust"];

const MOCK_MODELS = [
  { name: "GPT-5", color: "oklch(0.78 0.12 250)" },
  { name: "Claude Sonnet 4.5", color: "oklch(0.8 0.11 35)" },
  { name: "Gemini 2.5 Pro", color: "oklch(0.78 0.11 160)" },
  { name: "DeepSeek V3", color: "oklch(0.78 0.12 320)" },
];

function buildMockCode(model: string, language: string, problem: string) {
  const header = `// ${model} · ${language}\n// Problem: ${problem.slice(0, 60)}${
    problem.length > 60 ? "…" : ""
  }\n`;
  if (language === "Python") {
    return `# ${model} · Python\n# ${problem.slice(0, 60)}\ndef solve(nums):\n    seen = {}\n    for i, n in enumerate(nums):\n        if (target := 9 - n) in seen:\n            return [seen[target], i]\n        seen[n] = i\n    return []\n\nif __name__ == "__main__":\n    print(solve([2, 7, 11, 15]))\n`;
  }
  if (language === "C++") {
    return `${header}#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nvector<int> solve(vector<int>& nums, int target) {\n    unordered_map<int,int> seen;\n    for (int i = 0; i < nums.size(); ++i) {\n        auto it = seen.find(target - nums[i]);\n        if (it != seen.end()) return {it->second, i};\n        seen[nums[i]] = i;\n    }\n    return {};\n}\n`;
  }
  return `${header}export function solve(nums: number[], target = 9): number[] {\n  const seen = new Map<number, number>();\n  for (let i = 0; i < nums.length; i++) {\n    const need = target - nums[i];\n    if (seen.has(need)) return [seen.get(need)!, i];\n    seen.set(nums[i], i);\n  }\n  return [];\n}\n`;
}

function rand(min: number, max: number) {
  return +(min + Math.random() * (max - min)).toFixed(1);
}

function generateCandidates(problem: string, language: string): Candidate[] {
  return MOCK_MODELS.map((m, i) => {
    const correctness = rand(78, 99);
    const style = rand(70, 98);
    const performance = rand(65, 99);
    const crossReview = rand(70, 97);
    const total = +(
      correctness * 0.35 +
      performance * 0.3 +
      crossReview * 0.25 +
      style * 0.1
    ).toFixed(1);
    return {
      id: String(i),
      model: m.name,
      color: m.color,
      code: buildMockCode(m.name, language, problem),
      scores: { correctness, style, performance, crossReview },
      total,
      runtimeMs: +rand(0.4, 8.5).toFixed(2),
      memoryKb: Math.round(rand(420, 2800)),
    };
  });
}

function Index() {
  const [stage, setStage] = useState<Stage>("input");
  const [problem, setProblem] = useState("");
  const [language, setLanguage] = useState("Python");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [copied, setCopied] = useState(false);

  const winner = candidates.length
    ? [...candidates].sort((a, b) => b.total - a.total)[0]
    : null;

  const handleSubmit = () => {
    if (!problem.trim()) {
      toast.error("문제 설명을 입력해주세요.");
      return;
    }
    const c = generateCandidates(problem, language);
    setCandidates(c);
    setStage("candidates");
  };

  const runScoring = () => {
    setStage("scoring");
    setTimeout(() => setStage("result"), 1800);
  };

  const reset = () => {
    setStage("input");
    setProblem("");
    setCandidates([]);
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
            <h1 className="text-lg font-semibold text-foreground">MultiVerify</h1>
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
          {i < steps.length - 1 && (
            <div className="mx-1 h-px w-6 bg-border" />
          )}
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
          문제를 입력하면,
          <br />
          <span
            className="bg-clip-text text-transparent"
            style={{ backgroundImage: "var(--gradient-primary)" }}
          >
            최고의 코드를 찾아드립니다
          </span>
        </h2>
        <p className="mt-4 text-base font-medium text-muted-foreground">
          여러 LLM이 동시에 답하고, 서로 검증하고, 성능까지 측정합니다.
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
            <label className="mb-2 block text-sm font-semibold text-foreground">
              언어
            </label>
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
          { icon: Code2, t: "다중 응답", d: "4개 LLM 동시 호출" },
          { icon: Cpu, t: "성능 측정", d: "C++ 기반 실측" },
          { icon: Trophy, t: "최적 추천", d: "가중치 기반 점수화" },
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
  candidates: Candidate[];
  language: string;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <div className="pt-4">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">후보 응답</h2>
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
        {candidates.map((c) => (
          <Card
            key={c.id}
            className="overflow-hidden rounded-2xl border-border/60"
            style={{ boxShadow: "var(--shadow-card)" }}
          >
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: c.color }}
                />
                <span className="text-sm font-semibold text-foreground">
                  {c.model}
                </span>
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
    "LLM 간 교차 검증 진행 중...",
    "C++ 벤치마크로 성능 측정 중...",
    "가중치 기반 종합 점수 계산 중...",
  ];
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center">
      <div
        className="flex h-16 w-16 items-center justify-center rounded-2xl text-primary-foreground"
        style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-soft)" }}
      >
        <Loader2 className="h-7 w-7 animate-spin" />
      </div>
      <h2 className="mt-6 text-2xl font-bold text-foreground">교차 검증 중</h2>
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
  onReset,
  onShowFinal,
}: {
  candidates: Candidate[];
  onReset: () => void;
  onShowFinal: () => void;
}) {
  const sorted = [...candidates].sort((a, b) => b.total - a.total);
  return (
    <div className="pt-4">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-foreground">검증 결과</h2>
          <p className="text-sm font-medium text-muted-foreground">
            가중치: 정확성 35% · 성능 30% · 교차검증 25% · 스타일 10%
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onReset} className="rounded-xl">
            <RotateCcw className="mr-1 h-4 w-4" />
            새 문제
          </Button>
          <Button
            onClick={onShowFinal}
            className="rounded-xl text-primary-foreground font-semibold"
            style={{ background: "var(--gradient-primary)" }}
          >
            최종 추천 코드 보기
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {sorted.map((c, i) => (
          <Card
            key={c.id}
            className={`rounded-2xl p-5 transition ${
              i === 0
                ? "border-primary/40 ring-2 ring-primary/20"
                : "border-border/60"
            }`}
            style={{
              boxShadow: i === 0 ? "var(--shadow-soft)" : "var(--shadow-card)",
            }}
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: c.color }}
                />
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
                <div className="text-2xl font-extrabold text-foreground">
                  {c.total}
                </div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Score
                </div>
              </div>
            </div>

            <div className="space-y-2.5">
              <ScoreBar label="정확성" value={c.scores.correctness} />
              <ScoreBar label="성능 (C++ 측정)" value={c.scores.performance} />
              <ScoreBar label="교차 검증" value={c.scores.crossReview} />
              <ScoreBar label="스타일" value={c.scores.style} />
            </div>
          </Card>
        ))}
      </div>
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
  winner: Candidate;
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
          <h2 className="text-2xl font-extrabold text-foreground">최종 추천 코드</h2>
          <p className="text-sm font-medium text-muted-foreground">
            교차 검증과 성능 측정을 통과한 최적의 코드입니다.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onBack} className="rounded-xl">
            검증 결과로
          </Button>
          <Button variant="ghost" onClick={onReset} className="rounded-xl">
            <RotateCcw className="mr-1 h-4 w-4" />
            새 문제
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
                <div className="text-sm font-bold text-foreground">
                  {winner.model}
                </div>
                <div className="text-xs font-medium text-muted-foreground">
                  {language} · 종합 점수 {winner.total}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Metric icon={Timer} label="실행 시간" value={`${winner.runtimeMs} ms`} />
              <Metric
                icon={MemoryStick}
                label="메모리"
                value={`${winner.memoryKb} KB`}
              />
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
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className="text-sm font-semibold text-foreground">{value}</div>
      </div>
    </div>
  );
}
