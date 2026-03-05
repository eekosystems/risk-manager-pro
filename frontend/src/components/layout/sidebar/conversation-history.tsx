import { format } from "date-fns";
import { Clock, MessageSquare } from "lucide-react";

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
      <div className="mb-1 mt-6 flex items-center px-2 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        <Clock size={12} className="mr-1.5" />
        Recent
      </div>

      {isLoading && <ConversationSkeleton />}

      {isError && (
        <p className="px-3 py-2 text-xs text-red-500">
          Failed to load conversations
        </p>
      )}

      {!isLoading && !isError && conversations?.length === 0 && (
        <EmptyState
          icon={MessageSquare}
          title="No conversations yet"
          description="Start a new conversation using one of the core functions above"
        />
      )}

      {!isLoading &&
        !isError &&
        conversations?.map((c) => (
          <button
            key={c.id}
            onClick={() => onConversationSelect(c.id)}
            className="nav-item-hover mb-0.5 flex w-full flex-col rounded-lg px-3 py-2 text-left"
          >
            <span className="truncate text-sm font-medium text-gray-700">
              {c.title}
            </span>
            <span className="text-[11px] text-gray-400">
              {format(new Date(c.updated_at), "MMM d, yyyy")}
            </span>
          </button>
        ))}
    </>
  );
}
