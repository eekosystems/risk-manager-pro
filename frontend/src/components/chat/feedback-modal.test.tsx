import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FeedbackModal } from "./feedback-modal";

const submitFeedback = vi.fn();

vi.mock("@/api/feedback", () => ({
  submitFeedback: (params: unknown) => submitFeedback(params),
}));

function renderModal(onClose = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <FeedbackModal
        conversationId="conv-1"
        messageId="msg-1"
        onClose={onClose}
      />
    </QueryClientProvider>,
  );
  return onClose;
}

describe("FeedbackModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    submitFeedback.mockResolvedValue({ id: "fb-1" });
  });

  it("requires both a rating and a comment before sending", async () => {
    renderModal();

    const send = screen.getByRole("button", { name: /Send feedback/i });
    expect(send).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /Useful/i }));
    expect(send).toBeDisabled();

    await userEvent.type(screen.getByRole("textbox"), "Good answer.");
    expect(send).toBeEnabled();
  });

  it("sends the rating and comment for the message it was opened on", async () => {
    renderModal();

    await userEvent.click(screen.getByRole("button", { name: /Needs work/i }));
    await userEvent.type(
      screen.getByRole("textbox"),
      "Should cite AC 150/5340-30.",
    );
    await userEvent.click(screen.getByRole("button", { name: /Send feedback/i }));

    await waitFor(() =>
      expect(submitFeedback).toHaveBeenCalledWith({
        conversationId: "conv-1",
        messageId: "msg-1",
        rating: "not_helpful",
        comment: "Should cite AC 150/5340-30.",
      }),
    );
  });

  it("trims the comment before sending", async () => {
    renderModal();

    await userEvent.click(screen.getByRole("button", { name: /Useful/i }));
    await userEvent.type(screen.getByRole("textbox"), "   Padded.   ");
    await userEvent.click(screen.getByRole("button", { name: /Send feedback/i }));

    await waitFor(() =>
      expect(submitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({ comment: "Padded." }),
      ),
    );
  });

  it("confirms what happens to the feedback after sending", async () => {
    renderModal();

    await userEvent.click(screen.getByRole("button", { name: /Useful/i }));
    await userEvent.type(screen.getByRole("textbox"), "Good.");
    await userEvent.click(screen.getByRole("button", { name: /Send feedback/i }));

    expect(await screen.findByText(/Thank you/i)).toBeInTheDocument();
    expect(screen.getByText(/permanent guidance/i)).toBeInTheDocument();
  });

  it("surfaces a failure instead of silently dropping the feedback", async () => {
    submitFeedback.mockRejectedValue(new Error("network"));

    renderModal();
    await userEvent.click(screen.getByRole("button", { name: /Useful/i }));
    await userEvent.type(screen.getByRole("textbox"), "Good.");
    await userEvent.click(screen.getByRole("button", { name: /Send feedback/i }));

    expect(await screen.findByText(/could not be sent/i)).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const onClose = renderModal();

    await userEvent.keyboard("{Escape}");

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
