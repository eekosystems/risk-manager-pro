import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ConversationTranscript } from "@/types/api";

import { ConversationTranscriptModal } from "./conversation-transcript-modal";

const getConversationTranscript = vi.fn();

vi.mock("@/api/chat", () => ({
  getConversationTranscript: (id: string) => getConversationTranscript(id),
}));

vi.mock("@/components/chat/markdown-content", () => ({
  MarkdownContent: ({ content }: { content: string }) => <div>{content}</div>,
}));

function makeTranscript(
  overrides: Partial<ConversationTranscript> = {},
): ConversationTranscript {
  return {
    id: "conv-1",
    title: "Runway incursion review",
    function_type: "general",
    created_at: "2026-08-30T10:00:00Z",
    updated_at: "2026-08-30T10:05:00Z",
    author: { id: "user-9", display_name: "Dana Analyst" },
    messages: [
      {
        id: "m1",
        role: "user",
        content: "What is the residual risk?",
        citations: null,
        created_at: "2026-08-30T10:00:00Z",
      },
      {
        id: "m2",
        role: "assistant",
        content: "The residual risk is Medium.",
        citations: null,
        created_at: "2026-08-30T10:01:00Z",
      },
    ],
    ...overrides,
  } as ConversationTranscript;
}

function renderModal(onClose = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <ConversationTranscriptModal conversationId="conv-1" onClose={onClose} />
    </QueryClientProvider>,
  );
  return onClose;
}

describe("ConversationTranscriptModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getConversationTranscript.mockResolvedValue(makeTranscript());
  });

  it("shows the transcript with the author attributed", async () => {
    renderModal();

    expect(await screen.findByText("Runway incursion review")).toBeInTheDocument();
    expect(screen.getAllByText("Dana Analyst").length).toBeGreaterThan(0);
    expect(screen.getByText("What is the residual risk?")).toBeInTheDocument();
    expect(screen.getByText("The residual risk is Medium.")).toBeInTheDocument();
  });

  it("tells the admin that the access was recorded", async () => {
    renderModal();

    expect(
      await screen.findByText(/recorded in the audit log/i),
    ).toBeInTheDocument();
  });

  it("offers no way to reply to or delete the conversation", async () => {
    renderModal();
    await screen.findByText("Runway incursion review");

    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("explains a permission failure in plain language", async () => {
    getConversationTranscript.mockRejectedValue({ response: { status: 403 } });

    renderModal();

    expect(
      await screen.findByText(/organization administrator role/i),
    ).toBeInTheDocument();
  });

  it("does not confirm that another organization's conversation exists", async () => {
    getConversationTranscript.mockRejectedValue({ response: { status: 404 } });

    renderModal();

    expect(
      await screen.findByText(/no longer exists, or it belongs to a different/i),
    ).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const onClose = renderModal();
    await screen.findByText("Runway incursion review");

    await userEvent.keyboard("{Escape}");

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
