import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RiskOutcomeSummary, SharePointRiskRow } from "@/api/sharepoint";
import type {
  MitigationItem,
  ResidualAssessment,
  RiskEntryListItem,
} from "@/types/api";

import { RiskListView } from "./risk-list-view";

const dbRisk: RiskEntryListItem = {
  id: "db-1",
  title: "Runway incursion at hold short line",
  hazard: "Runway incursion at hold short line",
  severity: 4,
  likelihood: "C",
  risk_level: "high",
  status: "mitigating",
  function_type: "risk_register",
  airport_identifier: "DEN",
  operational_domain: null,
  hazard_category_5m: null,
  record_status: "open",
  validation_status: "rmp_validated",
  source: "manual_entry",
  residual_severity: null,
  residual_likelihood: null,
  residual_risk_level: null,
  source_document_url: null,
  mitigations: [{ id: "m-1", title: "Hold-short signage", status: "pending" }],
  latest_assessment: null,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const proposal: ResidualAssessment = {
  id: "assessment-1",
  risk_entry_id: "db-1",
  status: "proposed",
  trigger: "mitigation.created",
  residual_severity: 4,
  residual_likelihood: "E",
  residual_risk_level: "medium",
  result: {
    tiers: [],
    alarp_status: "ALARP achieved",
    rationale: "Signage lowers likelihood.",
    sources: [],
  },
  error_code: null,
  created_at: "2026-09-23T00:00:00Z",
  completed_at: "2026-09-23T00:01:00Z",
  decided_at: null,
};

function spRow(
  hazard: string,
  riskLevel: string,
  extra: Partial<SharePointRiskRow> = {},
): SharePointRiskRow {
  return {
    airport_identifier: "DEN",
    hazard,
    severity: 2,
    likelihood: "D",
    risk_level: riskLevel,
    source_file: "srmd.pdf",
    source_url: null,
    residual_severity: null,
    residual_likelihood: null,
    residual_risk_level: null,
    mitigations: [],
    ...extra,
  };
}

const summary: RiskOutcomeSummary = {
  airports: ["DEN"],
  risks: [
    spRow("Foreign Object Debris (FOD)", "low"),
    spRow("FOD - Clean Soil hauled", "medium", {
      severity: 3,
      likelihood: "C",
      residual_severity: 2,
      residual_likelihood: "D",
      residual_risk_level: "low",
      mitigations: ["Cover loads in transit", "Sweep haul route daily"],
    }),
  ],
  notes: [],
  generated_at: 0,
  status: "ready",
  scanned: 1,
  total: 1,
  last_scan_completed_at: 0,
};

const editorMitigation: MitigationItem = {
  id: "m-1",
  risk_entry_id: "db-1",
  title: "Hold-short signage",
  description: "Hold-short signage",
  assignee: null,
  due_date: null,
  verification_method: null,
  status: "pending",
  completed_at: null,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const mocks = vi.hoisted(() => ({
  dbRisks: [] as RiskEntryListItem[],
  canEdit: true,
  addToast: vi.fn(),
  deleteMutate: vi.fn(),
  importMutate: vi.fn(),
  confirmMutate: vi.fn(),
  updateMutate: vi.fn(),
}));

function mutation(mutate = vi.fn()) {
  return { mutate, isPending: false };
}

vi.mock("@/hooks/use-risks", () => ({
  useRisks: () => ({ data: { data: mocks.dbRisks }, isLoading: false }),
  useDeleteRisk: () => mutation(mocks.deleteMutate),
  useImportSrmdHazards: () => mutation(mocks.importMutate),
  useConfirmResidualAssessment: () => mutation(mocks.confirmMutate),
  useDismissResidualAssessment: () => mutation(),
  useRequestResidualAssessment: () => mutation(),
  useMitigations: () => ({ data: [editorMitigation], isLoading: false }),
  useCreateMitigation: () => mutation(),
  useUpdateMitigation: () => mutation(mocks.updateMutate),
  useDeleteMitigation: () => mutation(),
}));

vi.mock("@/hooks/use-user-role", () => ({
  useUserRole: () => ({ canEdit: mocks.canEdit }),
}));

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ addToast: mocks.addToast }),
}));

vi.mock("@/api/sharepoint", () => ({
  getRiskOutcomeSummary: () => Promise.resolve(summary),
}));

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <RiskListView onSelectRisk={vi.fn()} onCreateNew={vi.fn()} />
    </QueryClientProvider>,
  );
}

function listedTitles(): string[] {
  return [
    "Runway incursion at hold short line",
    "Foreign Object Debris (FOD)",
    "FOD - Clean Soil hauled",
  ].filter((title) => screen.queryAllByText(title).length > 0);
}

function rowFor(title: string): HTMLElement {
  const [titleEl] = screen.getAllByText(title, {
    selector: "span.font-semibold",
  });
  const row = titleEl?.closest(".grid");
  if (!(row instanceof HTMLElement)) throw new Error(`no row for ${title}`);
  return row;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.dbRisks = [dbRisk];
  mocks.canEdit = true;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("RiskListView filters", () => {
  it("applies the risk-level filter to SharePoint and DB rows alike", async () => {
    renderView();
    await screen.findAllByText("Foreign Object Debris (FOD)");

    await userEvent.selectOptions(
      screen.getByDisplayValue("All Risk Levels"),
      "low",
    );

    expect(listedTitles()).toEqual(["Foreign Object Debris (FOD)"]);
  });

  it("applies the status filter to SharePoint rows", async () => {
    renderView();
    await screen.findAllByText("Foreign Object Debris (FOD)");

    await userEvent.selectOptions(
      screen.getByDisplayValue("All Statuses"),
      "mitigating",
    );

    expect(listedTitles()).toEqual(["Runway incursion at hold short line"]);
  });

  it("says so when no row matches the filters", async () => {
    renderView();
    await screen.findAllByText("Foreign Object Debris (FOD)");

    await userEvent.selectOptions(
      screen.getByDisplayValue("All Statuses"),
      "closed",
    );

    expect(
      screen.getByText(
        "No risk entries match the selected status and risk level.",
      ),
    ).toBeInTheDocument();
  });
});

describe("RiskListView initial risk, residual risk and mitigations", () => {
  it("shows an SRMD hazard's initial cell, residual cell and mitigations", async () => {
    renderView();
    await screen.findAllByText("FOD - Clean Soil hauled");

    const row = within(rowFor("FOD - Clean Soil hauled"));
    expect(row.getByText("C3")).toBeInTheDocument();
    expect(row.getByText("D4")).toBeInTheDocument();
    expect(row.getByText("• Cover loads in transit")).toBeInTheDocument();
    expect(row.getByText("• Sweep haul route daily")).toBeInTheDocument();
    expect(row.getByText("Import SRMD hazards to edit")).toBeInTheDocument();
    expect(row.queryByText("Edit mitigations")).not.toBeInTheDocument();
  });

  it("imports the SRMD hazards still read from the scan", async () => {
    renderView();
    await screen.findAllByText("FOD - Clean Soil hauled");

    await userEvent.click(
      screen.getByRole("button", { name: /Import 2 SRMD hazards/ }),
    );

    expect(mocks.importMutate).toHaveBeenCalledTimes(1);
  });

  it("confirms a proposed residual", async () => {
    mocks.dbRisks = [{ ...dbRisk, latest_assessment: proposal }];
    renderView();
    await screen.findAllByText("Foreign Object Debris (FOD)");

    const row = within(rowFor("Runway incursion at hold short line"));
    expect(row.getByText("Proposed")).toBeInTheDocument();
    expect(row.getByText("E2")).toBeInTheDocument();
    await userEvent.click(row.getByRole("button", { name: "Confirm" }));

    expect(mocks.confirmMutate).toHaveBeenCalledWith(
      "assessment-1",
      expect.anything(),
    );
  });

  it("saves an edited mitigation from the inline editor", async () => {
    renderView();
    await screen.findAllByText("Foreign Object Debris (FOD)");

    await userEvent.click(
      within(rowFor("Runway incursion at hold short line")).getByRole(
        "button",
        {
          name: "Edit mitigations",
        },
      ),
    );
    const field = screen.getByLabelText("Mitigation: Hold-short signage");
    await userEvent.clear(field);
    await userEvent.type(field, "Hold-short signage with flashing beacons");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(mocks.updateMutate).toHaveBeenCalledWith(
      {
        mitigationId: "m-1",
        payload: {
          title: "Hold-short signage with flashing beacons",
          description: "Hold-short signage with flashing beacons",
        },
      },
      expect.anything(),
    );
  });

  it("gives viewers a read-only row", async () => {
    mocks.canEdit = false;
    mocks.dbRisks = [{ ...dbRisk, latest_assessment: proposal }];
    renderView();
    await screen.findAllByText("Foreign Object Debris (FOD)");

    expect(
      screen.queryByRole("button", { name: "Confirm" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Edit mitigations")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Import/ }),
    ).not.toBeInTheDocument();
  });
});

describe("RiskListView delete", () => {
  const secondDbRisk: RiskEntryListItem = {
    ...dbRisk,
    id: "db-2",
    title: "Wildlife strike on approach",
    hazard: "Wildlife strike on approach",
  };

  function deleteButton(title: string): HTMLElement {
    return within(rowFor(title)).getByTitle(/delete/i);
  }

  it("keeps a second row armed after the first row's arm window expires", async () => {
    mocks.dbRisks = [dbRisk, secondDbRisk];
    renderView();
    await screen.findAllByText("Wildlife strike on approach");
    vi.useFakeTimers();

    fireEvent.click(deleteButton("Runway incursion at hold short line"));
    act(() => vi.advanceTimersByTime(2000));
    fireEvent.click(deleteButton("Wildlife strike on approach"));
    act(() => vi.advanceTimersByTime(1500));
    fireEvent.click(deleteButton("Wildlife strike on approach"));

    expect(mocks.deleteMutate).toHaveBeenCalledTimes(1);
    expect(mocks.deleteMutate.mock.calls[0]?.[0]).toBe("db-2");
  });

  it("shows an error toast when the delete request fails", async () => {
    renderView();
    await screen.findAllByText("Runway incursion at hold short line");

    await userEvent.click(deleteButton("Runway incursion at hold short line"));
    await userEvent.click(deleteButton("Runway incursion at hold short line"));

    const options = mocks.deleteMutate.mock.calls[0]?.[1] as {
      onError: () => void;
    };
    options.onError();

    expect(mocks.addToast).toHaveBeenCalledWith("Could not delete the hazard", "error");
  });
});
