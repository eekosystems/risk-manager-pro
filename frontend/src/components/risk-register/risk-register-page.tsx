import { clsx } from "clsx";
import { useState } from "react";

import { useRisk, useUpdateRisk } from "@/hooks/use-risks";
import { useUserRole } from "@/hooks/use-user-role";
import type { CreateRiskEntryRequest } from "@/types/api";

import { CreateRiskModal } from "./create-risk-modal";
import { PortfolioView } from "./portfolio-view";
import { RiskDetailView } from "./risk-detail-view";
import { RiskListView } from "./risk-list-view";
// SyncReviewPanel import retained as a comment so the tab can be re-enabled
// quickly when the sync workflow is needed again.
// import { SyncReviewPanel } from "./sync-review-panel";

type RRTab = "list" | "sync" | "portfolio";

// Feature flag — flip to `true` to restore the "Sync Review" tab in the
// Risk Register header. Hidden for now because the dual-register sync
// workflow isn't in active use; all wiring (SyncReviewPanel, listPendingSyncChanges,
// the pending-count badge) is preserved so re-enabling is a one-line change.
const SYNC_REVIEW_TAB_ENABLED = false;

interface RiskRegisterPageProps {
  onStartChatEntry: () => void;
}

export function RiskRegisterPage({ onStartChatEntry }: RiskRegisterPageProps) {
  const [selectedRiskId, setSelectedRiskId] = useState<string | null>(null);
  const [editingRiskId, setEditingRiskId] = useState<string | null>(null);
  const [tab, setTab] = useState<RRTab>("list");

  const { isPlatformAdmin } = useUserRole();
  const updateMutation = useUpdateRisk();
  const { data: editingRisk } = useRisk(editingRiskId);

  function handleEdit(payload: CreateRiskEntryRequest) {
    if (!editingRiskId) return;
    updateMutation.mutate(
      { riskId: editingRiskId, payload },
      {
        onSuccess: () => {
          setEditingRiskId(null);
        },
      },
    );
  }

  // Detail view takes over the whole pane.
  if (selectedRiskId) {
    return (
      <div className="flex-1 overflow-y-auto">
        <RiskDetailView
          riskId={selectedRiskId}
          onBack={() => setSelectedRiskId(null)}
          onEdit={() => setEditingRiskId(selectedRiskId)}
        />
        {editingRiskId && editingRisk && (
          <CreateRiskModal
            onClose={() => setEditingRiskId(null)}
            onSubmit={handleEdit}
            isPending={updateMutation.isPending}
            existingRisk={editingRisk}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="border-b border-gray-200 bg-white px-6 pt-4">
        <div className="flex gap-2">
          <TabButton active={tab === "list"} onClick={() => setTab("list")}>
            Risk Register
          </TabButton>
          {SYNC_REVIEW_TAB_ENABLED && (
            <TabButton active={tab === "sync"} onClick={() => setTab("sync")}>
              Sync Review
            </TabButton>
          )}
          {isPlatformAdmin && (
            <TabButton
              active={tab === "portfolio"}
              onClick={() => setTab("portfolio")}
            >
              FG Portfolio
            </TabButton>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === "list" && (
          <RiskListView
            onSelectRisk={setSelectedRiskId}
            onCreateNew={onStartChatEntry}
          />
        )}
        {/* Sync Review pane intentionally omitted while SYNC_REVIEW_TAB_ENABLED is false. */}
        {tab === "portfolio" && isPlatformAdmin && <PortfolioView />}
      </div>

      {editingRiskId && editingRisk && (
        <CreateRiskModal
          onClose={() => setEditingRiskId(null)}
          onSubmit={handleEdit}
          isPending={updateMutation.isPending}
          existingRisk={editingRisk}
        />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "relative rounded-t-lg px-4 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-brand-50 text-brand-700"
          : "text-slate-500 hover:bg-gray-50 hover:text-slate-700",
      )}
    >
      {children}
      {badge !== undefined && (
        <span className="ml-2 inline-flex items-center justify-center rounded-full bg-brand-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
          {badge}
        </span>
      )}
    </button>
  );
}
