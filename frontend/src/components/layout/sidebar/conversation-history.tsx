import { format } from "date-fns";
import { CheckCircle, Clock, MessageSquare } from "lucide-react";

import { ConversationSkeleton } from "@/components/ui/conversation-skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useConversations } from "@/hooks/use-chat";

interface ConversationHistoryProps {
  onConversationSelect: (id: string) => void;
}

export function ConversationHistory({
  onConversationSelect,
}: ConversationHistoryProps) {
  const { data: conversations, isLoading, isError } = useConversations();

  return (
    <>
      <div className="mb-1 mt-6 flex items-center px-2 text-[11px] font-bold uppercase tracking-wider text-slate-900">
        Recent Sessions
      </div>

      {isLoading && <ConversationSkeleton />}

      {isError && (
        <p className="px-3 py-2 text-xs text-red-500">
          Failed to load sessions
        </p>
      )}

      {!isLoading && !isError && conversations?.length === 0 && (
        <EmptyState
          icon={MessageSquare}
          title="No sessions yet"
          description="Start a new session using one of the core functions above"
        />
      )}

      {!isLoading &&
        !isError &&
        conversations?.map((c) => (
          <button
            key={c.id}
            onClick={() => onConversationSelect(c.id)}
            className="nav-item-hover mb-0.5 flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-100">
              <MessageSquare size={14} className="text-gray-500" />
            </div>
            <div className="flex flex-1 flex-col overflow-hidden">
              <span className="truncate text-[13px] font-medium text-gray-700">
                {c.title}
              </span>
              <span className="text-[11px] text-gray-400">
                {format(new Date(c.updated_at), "MMM d, yyyy")}
              </span>
            </div>
            <StatusBadge updatedAt={c.updated_at} />
          </button>
        ))}
    </>
  );
}

interface StatusBadgeProps {
  updatedAt: string;
}

function StatusBadge({ updatedAt }: StatusBadgeProps) {
  const hoursSinceUpdate =
    (Date.now() - new Date(updatedAt).getTime()) / (1000 * 60 * 60);
  const isRecent = hoursSinceUpdate < 24;

  if (isRecent) {
    return (
      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-brand-500">
        <CheckCircle size={12} className="text-white" />
      </div>
    );
  }

  return (
    <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-yellow-300 to-yellow-400">
      <Clock size={12} className="text-amber-800" />
    </div>
  );
}
