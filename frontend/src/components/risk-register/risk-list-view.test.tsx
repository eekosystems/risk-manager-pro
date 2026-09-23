import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { RiskOutcomeSummary, SharePointRiskRow } from "@/api/sharepoint";
import type { RiskEntryListItem } from "@/types/api";

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
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

function spRow(hazard: string, riskLevel: string): SharePointRiskRow {
  return {
    airport_identifier: "DEN",
    hazard,
    severity: 2,
    likelihood: "D",
    risk_level: riskLevel,
    source_file: "srmd.pdf",
    source_url: null,
  };
}

const summary: RiskOutcomeSummary = {
  airports: ["DEN"],
  risks: [
    spRow("Foreign Object Debris (FOD)", "low"),
    spRow("FOD - Clean Soil hauled", "medium"),
  ],
  notes: [],
  generated_at: 0,
  status: "ready",
  scanned: 1,
  total: 1,
  last_scan_completed_at: 0,
};

vi.mock("@/hooks/use-risks", () => ({
  useRisks: () => ({ data: { data: [dbRisk] }, isLoading: false }),
  useDeleteRisk: () => ({ mutate: vi.fn(), isPending: false }),
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
