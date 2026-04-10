import ReactMarkdown, { type Components } from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

const components: Components = {
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
      return (
        <code className="text-[13px]">{children}</code>
      );
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
  a: ({ children, href }) => (
    <a
      href={href}
      className="font-medium text-brand-600 underline decoration-brand-300 hover:text-brand-700"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-3 border-gray-200" />,
  strong: ({ children, node }) => {
    // Extract text from HAST node (most reliable) with React children fallback
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

interface MarkdownContentProps {
  content: string;
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSanitize]}
      components={components}
    >
      {content}
    </ReactMarkdown>
  );
}
