import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/cn";

import { CodeBlock } from "./CodeBlock";

interface HastNode {
  type: string;
  value?: string;
  tagName?: string;
  properties?: Record<string, unknown>;
  children?: HastNode[];
}

function textOf(node: HastNode): string {
  if (node.type === "text") return node.value ?? "";
  return (node.children ?? []).map(textOf).join("");
}

function languageOf(node: HastNode | undefined): string | null {
  const className = node?.properties?.className;
  if (!Array.isArray(className)) return null;
  const match = className.find((name): name is string => typeof name === "string" && name.startsWith("language-"));
  return match ? match.slice("language-".length) : null;
}

const components: Components = {
  pre({ node, children }) {
    const code = (node as HastNode | undefined)?.children?.find((child) => child.tagName === "code");
    return (
      <CodeBlock language={languageOf(code)} code={code ? textOf(code).replace(/\n$/, "") : ""}>
        {children}
      </CodeBlock>
    );
  },
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer nofollow">
        {children}
      </a>
    );
  },
  // Model output can be steered by retrieved documents, so remote images are
  // never loaded automatically (they could leak data through the URL).
  img({ src, alt }) {
    if (!src) return null;
    return (
      <a href={src} target="_blank" rel="noopener noreferrer nofollow">
        {alt ? `Image: ${alt}` : "Image link"}
      </a>
    );
  },
};

const remarkPlugins = [remarkGfm];
const rehypePlugins = [[rehypeHighlight, { detect: false }]] as Parameters<typeof ReactMarkdown>[0]["rehypePlugins"];

/** Renders untrusted Markdown: raw HTML is skipped and URLs are sanitized. */
export const Markdown = memo(function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn("markdown", className)}>
      <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins} components={components} skipHtml>
        {content}
      </ReactMarkdown>
    </div>
  );
});
