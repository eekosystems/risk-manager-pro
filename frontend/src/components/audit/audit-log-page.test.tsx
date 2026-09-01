import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuditEntry } from "@/types/api";

import { AuditLogPage } from "./audit-log-page";

const useAuditEntries = vi.fn();
const isAdmin = vi.fn(() => true);

vi.mock("@/hooks/use-audit", () => ({
  useAuditEntries: (params: unknown) => useAuditEntries(params),
  useAuditFilterOptions: () => ({
    data: { actions: [], resource_types: [], outcomes: [] },
  }),
}));

vi.mock("@/hooks/use-user-role", () => ({
  useUserRole: () => ({ isAdmin: isAdmin() }),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

const transcriptModal = vi.fn();
vi.mock("./conversation-transcript-modal", () => ({
  ConversationTranscriptModal: ({ conversationId }: { conversationId: string }) => {
    transcriptModal(conversationId);
    return <div data-testid="transcript-modal">{conversationId}</div>;
  },
}));

function makeEntry(overrides: Partial<AuditEntry> = {}): AuditEntry {
  return {
    id: "audit-1",
    timestamp: "2026-08-30T10:00:00Z",
    user_id: "11111111-2222-3333-4444-555555555555",
    action: "chat.message_sent",
    resource_type: "conversation",
    resource_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    ip_address: "10.0.0.1",
    correlation_id: "corr-1",
    outcome: "success",
    organization_id: "org-1",
    ...overrides,
  };
}

function setEntries(entries: AuditEntry[]) {
  useAuditEntries.mockReturnValue({
    data: { data: entries, total: entries.length },
    isLoading: false,
  });
}

describe("AuditLogPage conversation links", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    isAdmin.mockReturnValue(true);
    setEntries([makeEntry()]);
  });

  it("offers admins a link into the conversation", () => {
    render(<AuditLogPage />);

    expect(screen.getByText("View chat")).toBeInTheDocument();
  });

  it("opens the transcript for the conversation named in the row", async () => {
    render(<AuditLogPage />);

    await userEvent.click(screen.getByText("View chat"));

    expect(screen.getByTestId("transcript-modal")).toBeInTheDocument();
    expect(transcriptModal).toHaveBeenCalledWith(
      "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    );
  });

  it("does not offer the link to non-admins", () => {
    // The endpoint refuses them anyway; the UI should not dangle the affordance.
    isAdmin.mockReturnValue(false);

    render(<AuditLogPage />);

    expect(screen.queryByText("View chat")).not.toBeInTheDocument();
  });

  it("does not offer the link on non-conversation entries", () => {
    setEntries([
      makeEntry({ resource_type: "document", action: "document.uploaded" }),
    ]);

    render(<AuditLogPage />);

    expect(screen.queryByText("View chat")).not.toBeInTheDocument();
  });

  it("does not offer the link when the row has no resource id", () => {
    setEntries([makeEntry({ resource_id: null })]);

    render(<AuditLogPage />);

    expect(screen.queryByText("View chat")).not.toBeInTheDocument();
  });
});
