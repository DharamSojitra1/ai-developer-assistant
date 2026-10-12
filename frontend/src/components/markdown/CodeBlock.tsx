import type { ReactNode } from "react";

import { CopyButton } from "../ui/CopyButton";

export function CodeBlock({ language, code, children }: { language: string | null; code: string; children: ReactNode }) {
  return (
    <div className="not-prose my-4 overflow-hidden rounded-panel border border-border bg-[#121214]">
      <div className="flex h-9 items-center justify-between border-b border-border bg-surface pl-3.5 pr-1.5">
        <span className="font-mono text-xs text-subtle">{language ?? "text"}</span>
        <CopyButton text={code} label="Copy code" showLabel />
      </div>
      <pre className="!my-0 overflow-x-auto px-4 py-3.5 font-mono text-[0.8125rem] leading-6 [&>code]:font-mono">
        {children}
      </pre>
    </div>
  );
}
