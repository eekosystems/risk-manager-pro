import { useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Citation } from "@/types/api";

/* ------------------------------------------------------------------ */
/*  Static components (no dependency on props)                        */
/* ------------------------------------------------------------------ */
const baseComponents: Partial<Components> = {
  h1: ({ children }) => (
    <h1 className="mb-3 mt-4 text-lg font-bold text-gray-900">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-3 text-base font-bold text-gray-900">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-3 text-sm font-bold text-gray-900">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="mb-2 text-sm leading-relaxed text-gray-800">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 ml-4 list-disc space-y-1 text-sm text-gray-800">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 ml-4 list-decimal space-y-1 text-sm text-gray-800">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  code: ({ children, className }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return <code className="text-[13px]">{children}</code>;
    }
    return (
      <code className="rounded bg-gray-100 px-1.5 py-0.5 text-[13px] font-mono text-brand-700">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="mb-2 overflow-x-auto rounded-lg bg-gray-900 p-3 text-gray-100">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-3 border-brand-300 pl-3 italic text-gray-600">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-gray-50">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="border border-gray-200 px-3 py-1.5 text-left text-xs font-semibold text-gray-700">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-gray-200 px-3 py-1.5 text-gray-700">
      {children}
    </td>
  ),
  hr: () => <hr className="my-3 border-gray-200" />,
  strong: ({ children, node }) => {
    let text = "";
    if (node?.children) {
      for (const child of node.children) {
        if (child.type === "text") text += child.value;
      }
    }
    if (!text) {
      text = Array.isArray(children) ? children.join("") : String(children ?? "");
    }
    text = text.trim().toLowerCase();
    if (text === "high") {
      return <strong className="font-semibold" style={{ color: "#dc2626" }}>{children}</strong>;
    }
    if (text === "medium" || text === "moderate") {
      return <strong className="font-semibold" style={{ color: "#d97706" }}>{children}</strong>;
    }
    if (text === "low") {
      return <strong className="font-semibold" style={{ color: "#16a34a" }}>{children}</strong>;
    }
    return <strong className="font-semibold text-gray-900">{children}</strong>;
  },
};

/* ------------------------------------------------------------------ */
/*  Inline citation tooltip                                           */
/* ------------------------------------------------------------------ */
const TIER_DOT: Record<string, string> = {
  High: "#10b981",
  Moderate: "#f59e0b",
  Low: "#9ca3af",
};

function CitationTooltip({
  citation,
  children,
  onClick,
}: {
  citation: Citation;
  children: React.ReactNode;
  onClick: () => void;
}) {
  const tier = citation.match_tier ?? "Moderate";
  const dotColor = TIER_DOT[tier] ?? TIER_DOT.Moderate;
  const name =
    citation.source.length > 50
      ? citation.source.slice(0, 47) + "..."
      : citation.source;

  return (
    <span className="group/cite relative inline">
      <button
        type="button"
        onClick={onClick}
        className="inline cursor-pointer rounded px-0.5 font-medium text-brand-600 transition-colors hover:bg-brand-50 hover:text-brand-700"
      >
        {children}
      </button>
      <span className="pointer-events-none invisible absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 rounded-lg bg-gray-900 px-3 py-2 text-left text-xs leading-relaxed text-white shadow-xl group-hover/cite:visible">
        <span className="block max-w-[240px] truncate font-medium">{name}</span>
        {citation.section && (
          <span className="block text-gray-400">{citation.section}</span>
        )}
        <span className="flex items-center gap-1.5 text-gray-400">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: dotColor }}
          />
          {tier} Match
        </span>
        <span className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-gray-900" />
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Pre-process markdown: convert [Source N] → clickable links        */
/* ------------------------------------------------------------------ */
function preprocessCitations(content: string): string {
  return content.replace(
    /\[Source (\d+)\]/g,
    "[\\[Source $1\\]](#citation-$1)",
  );
}

/* ------------------------------------------------------------------ */
/*  Public component                                                  */
/* ------------------------------------------------------------------ */
interface MarkdownContentProps {
  content: string;
  citations?: Citation[] | undefined;
  onCitationClick?: ((index: number) => void) | undefined;
}

export function MarkdownContent({
  content,
  citations,
  onCitationClick,
}: MarkdownContentProps) {
  const processed = citations?.length
    ? preprocessCitations(content)
    : content;

  const components: Components = useMemo(
    () => ({
      ...baseComponents,
      a: ({ children, href }) => {
        const match = href?.match(/^#citation-(\d+)$/);
        if (match && citations) {
          const idx = parseInt(match[1]!, 10) - 1;
          const citation = citations[idx];
          if (citation) {
            return (
              <CitationTooltip
                citation={citation}
                onClick={() => onCitationClick?.(idx)}
              >
                {children}
              </CitationTooltip>
            );
          }
        }
        return (
          <a
            href={href}
            className="font-medium text-brand-600 underline decoration-brand-300 hover:text-brand-700"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        );
      },
    }),
    [citations, onCitationClick],
  );

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={components}
    >
      {processed}
    </ReactMarkdown>
  );
}
