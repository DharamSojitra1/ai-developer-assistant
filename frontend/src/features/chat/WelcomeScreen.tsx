import { BookOpen, Calculator, Code2, Lightbulb } from "lucide-react";
import type { ReactNode } from "react";

const STARTERS: { icon: ReactNode; title: string; prompt: string }[] = [
  {
    icon: <Code2 aria-hidden />,
    title: "Write a FastAPI endpoint",
    prompt: "Write a FastAPI endpoint that validates a JSON body with Pydantic and returns a typed response.",
  },
  {
    icon: <BookOpen aria-hidden />,
    title: "Search my documents",
    prompt: "Search my knowledge base and summarize what it says about deployment.",
  },
  {
    icon: <Calculator aria-hidden />,
    title: "Run a quick calculation",
    prompt: "What is 18% of 2,340, and what is the total after adding it?",
  },
  {
    icon: <Lightbulb aria-hidden />,
    title: "Explain a concept",
    prompt: "Explain the difference between async/await and threads in Python, with a short example.",
  },
];

function greeting(now = new Date()): string {
  const hour = now.getHours();
  if (hour < 5) return "Working late";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function WelcomeHeading() {
  return (
    <div className="mb-8 text-center">
      <p className="text-sm text-muted">{greeting()}</p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight sm:text-[1.75rem]">What are we building today?</h1>
    </div>
  );
}

export function StarterPrompts({ onPick, disabled }: { onPick: (prompt: string) => void; disabled?: boolean }) {
  return (
    <ul className="mt-6 grid gap-2 sm:grid-cols-2" aria-label="Suggested prompts">
      {STARTERS.map((starter) => (
        <li key={starter.title}>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onPick(starter.prompt)}
            className="flex h-full w-full items-start gap-3 rounded-panel border border-border px-3.5 py-3 text-left transition-colors hover:border-border-strong hover:bg-surface disabled:opacity-50"
          >
            <span className="mt-0.5 text-subtle [&_svg]:size-4">{starter.icon}</span>
            <span className="min-w-0">
              <span className="block text-sm font-medium text-fg">{starter.title}</span>
              <span className="mt-0.5 line-clamp-2 block text-[0.8125rem] leading-5 text-muted">{starter.prompt}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
