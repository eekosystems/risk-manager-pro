import { clsx } from "clsx";
import { Bot, ChevronRight, MessageSquare } from "lucide-react";

import { AiStatusCard } from "@/components/layout/panel/ai-status-card";
import { ConversationHistory } from "@/components/layout/sidebar/conversation-history";

interface RightPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  onConversationSelect: (id: string) => void;
}

export function RightPanel({
  isOpen,
  onToggle,
  onConversationSelect,
}: RightPanelProps) {
  return (
    <aside
      aria-label="Recent sessions and status"
      className={clsx(
        "relative flex flex-col border-l border-gray-200 bg-white transition-all duration-300",
        isOpen ? "w-[300px] min-w-[300px]" : "w-[60px] min-w-[60px]",
      )}
    >
      {/* Edge-centered toggle */}
      <button
        onClick={onToggle}
        aria-label={isOpen ? "Collapse panel" : "Expand panel"}
        className="absolute left-0 top-1/2 z-30 -translate-x-1/2 -translate-y-1/2 rounded-lg border border-gray-200 bg-white px-0.5 py-4 text-gray-400 shadow-md transition-colors hover:bg-brand-50 hover:text-brand-500"
      >
        <ChevronRight
          size={16}
          className={clsx("transition-transform", !isOpen && "rotate-180")}
        />
      </button>

      {isOpen ? (
        <div className="flex min-w-[300px] flex-col h-full overflow-y-auto px-3 py-4">
          <ConversationHistory onConversationSelect={onConversationSelect} />
          <div className="mt-auto px-2 pt-4">
            <AiStatusCard />
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center h-full py-3">
          {/* Collapsed section icons */}
          <nav className="flex flex-col items-center gap-1">
            <button
              onClick={onToggle}
              aria-label="Recent sessions"
              title="Recent sessions"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <MessageSquare size={20} />
            </button>
          </nav>

          {/* AI status at bottom */}
          <div className="mt-auto">
            <button
              onClick={onToggle}
              aria-label="AI status"
              title="AI status"
              className="flex h-10 w-10 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-brand-50 hover:text-brand-500"
            >
              <Bot size={20} />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
