import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./settings-page";

const role = { isPlatformAdmin: false, isAdmin: false };

vi.mock("@/hooks/use-user-role", () => ({
  useUserRole: () => role,
}));

// Each tab body pulls its own data; the gating is what is under test here.
// The factories are inlined because vi.mock is hoisted above any helper.
vi.mock("./tabs/rag-settings-tab", () => ({
  RagSettingsTab: () => <div>RagSettingsTab</div>,
}));
vi.mock("./tabs/indexed-files-tab", () => ({
  IndexedFilesTab: () => <div>IndexedFilesTab</div>,
}));
vi.mock("./tabs/prompts-tab", () => ({
  PromptsTab: () => <div>PromptsTab</div>,
}));
vi.mock("./tabs/model-preferences-tab", () => ({
  ModelPreferencesTab: () => <div>ModelPreferencesTab</div>,
}));
vi.mock("./tabs/qaqc-settings-tab", () => ({
  QaqcSettingsTab: () => <div>QaqcSettingsTab</div>,
}));
vi.mock("./tabs/users-roles-tab", () => ({
  UsersRolesTab: () => <div>UsersRolesTab</div>,
}));
vi.mock("./tabs/feedback-tab", () => ({
  FeedbackTab: () => <div>FeedbackTab</div>,
}));
vi.mock("./tabs/client-accounts-tab", () => ({
  ClientAccountsTab: () => <div>ClientAccountsTab</div>,
}));

const PLATFORM_ONLY = [
  "RAG Settings",
  "Model Preferences",
  "Prompts",
  "QA/QC Reviewers",
  "Client Accounts",
  "Feedback & Training",
];

function renderSettings() {
  render(<SettingsPage onClose={vi.fn()} />);
}

describe("SettingsPage visibility", () => {
  beforeEach(() => {
    role.isPlatformAdmin = false;
    role.isAdmin = false;
  });

  it("shows a client analyst their files and nothing else", () => {
    renderSettings();

    expect(screen.getByText("Indexed Files")).toBeInTheDocument();
    for (const label of PLATFORM_ONLY) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
    expect(screen.queryByText("Users & Roles")).not.toBeInTheDocument();
  });

  it("opens a client on Indexed Files rather than a tab they cannot see", () => {
    renderSettings();

    // Regression: the panel defaulted to RAG Settings, so a client landed on
    // an empty screen.
    expect(screen.getByText("IndexedFilesTab")).toBeInTheDocument();
  });

  it("gives a client's own account admin team management too", () => {
    role.isAdmin = true;

    renderSettings();

    expect(screen.getByText("Indexed Files")).toBeInTheDocument();
    expect(screen.getByText("Users & Roles")).toBeInTheDocument();
    for (const label of PLATFORM_ONLY) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it("gives a platform admin everything", () => {
    role.isPlatformAdmin = true;
    role.isAdmin = true;

    renderSettings();

    for (const label of PLATFORM_ONLY) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText("Indexed Files")).toBeInTheDocument();
    expect(screen.getByText("Users & Roles")).toBeInTheDocument();
  });

  it("keeps AI behaviour settings away from a client account admin", () => {
    // An account admin runs their own team; they do not tune the model,
    // the prompts, or retrieval for everyone.
    role.isAdmin = true;

    renderSettings();

    expect(screen.queryByText("Prompts")).not.toBeInTheDocument();
    expect(screen.queryByText("Model Preferences")).not.toBeInTheDocument();
    expect(screen.queryByText("RAG Settings")).not.toBeInTheDocument();
  });
});
