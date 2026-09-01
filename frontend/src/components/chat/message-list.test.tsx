import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "@/types/api";

import { MessageList } from "./message-list";

const exportTextToDocx = vi.fn();
const exportTextToPdf = vi.fn();

vi.mock("@/lib/export-docx", () => ({
  exportTextToDocx: (content: string) => exportTextToDocx(content),
}));

vi.mock("@/lib/export-pdf", () => ({
  exportTextToPdf: (content: string) => exportTextToPdf(content),
}));

vi.mock("./feedback-modal", () => ({
  FeedbackModal: ({ messageId }: { messageId: string }) => (
    <div data-testid="feedback-modal">{messageId}</div>
  ),
}));

function assistantMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "msg-1",
    role: "assistant",
    content: "The residual risk is Medium.",
    citations: null,
    created_at: "2026-08-31T12:00:00Z",
    ...overrides,
  } as ChatMessage;
}

function renderList(messages: ChatMessage[], conversationId: string | null = "conv-1") {
  return render(
    <MessageList
      messages={messages}
      isTyping={false}
      conversationId={conversationId}
    />,
  );
}

describe("MessageList export actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom does not implement scrollIntoView, which the list calls on mount.
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("offers a Word export alongside the PDF export", async () => {
    renderList([assistantMessage()]);

    expect(screen.getByRole("button", { name: /Export PDF/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export Word/i })).toBeInTheDocument();
  });

  it("exports the message content to Word when clicked", async () => {
    renderList([assistantMessage()]);

    await userEvent.click(screen.getByRole("button", { name: /Export Word/i }));

    expect(exportTextToDocx).toHaveBeenCalledWith("The residual risk is Medium.");
    expect(exportTextToPdf).not.toHaveBeenCalled();
  });

  it("does not offer exports on user messages", () => {
    renderList([assistantMessage({ id: "msg-user", role: "user" })]);

    expect(screen.queryByRole("button", { name: /Export Word/i })).not.toBeInTheDocument();
  });

  it("offers a Feedback button alongside the exports", () => {
    renderList([assistantMessage()]);

    expect(screen.getByRole("button", { name: /Feedback/i })).toBeInTheDocument();
  });

  it("opens the feedback modal for the message it was clicked on", async () => {
    renderList([assistantMessage({ id: "msg-42" })]);

    await userEvent.click(screen.getByRole("button", { name: /Feedback/i }));

    expect(screen.getByTestId("feedback-modal")).toHaveTextContent("msg-42");
  });

  it("hides Feedback before the conversation exists to attach it to", () => {
    renderList([assistantMessage()], null);

    expect(
      screen.queryByRole("button", { name: /Feedback/i }),
    ).not.toBeInTheDocument();
  });
});
