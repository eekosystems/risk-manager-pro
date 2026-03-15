import { useState } from "react";

import { useCreateRisk, useRisk, useUpdateRisk } from "@/hooks/use-risks";
import type { CreateRiskEntryRequest } from "@/types/api";

import { CreateRiskModal } from "./create-risk-modal";
import { RiskDetailView } from "./risk-detail-view";
import { RiskListView } from "./risk-list-view";

export function RiskRegisterPage() {
  const [selectedRiskId, setSelectedRiskId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingRiskId, setEditingRiskId] = useState<string | null>(null);

  const createMutation = useCreateRisk();
  const updateMutation = useUpdateRisk();
  const { data: editingRisk } = useRisk(editingRiskId);

  function handleCreate(payload: CreateRiskEntryRequest) {
    createMutation.mutate(payload, {
      onSuccess: () => {
        setShowCreateModal(false);
      },
    });
  }

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

  return (
    <div className="flex-1 overflow-y-auto">
      {selectedRiskId ? (
        <RiskDetailView
          riskId={selectedRiskId}
          onBack={() => setSelectedRiskId(null)}
          onEdit={() => setEditingRiskId(selectedRiskId)}
        />
      ) : (
        <RiskListView
          onSelectRisk={setSelectedRiskId}
          onCreateNew={() => setShowCreateModal(true)}
        />
      )}

      {/* Create modal */}
      {showCreateModal && (
        <CreateRiskModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={handleCreate}
          isPending={createMutation.isPending}
        />
      )}

      {/* Edit modal */}
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
