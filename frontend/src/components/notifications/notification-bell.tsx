import { formatDistanceToNow } from "date-fns";
import { Bell, CheckCheck, MessageSquare, ShieldAlert } from "lucide-react";
import { useRef, useState } from "react";

import { useClickOutside } from "@/hooks/use-click-outside";
import {
  useMarkAllRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/hooks/use-notifications";
import type { NotificationItem } from "@/types/api";

import type { AppView } from "../layout/app-layout";

const TYPE_ICONS: Record<string, typeof MessageSquare> = {
  chat_response: MessageSquare,
  risk_created: ShieldAlert,
};

const TYPE_COLORS: Record<string, string> = {
  chat_response: "text-brand-500 bg-brand-50",
  risk_created: "text-red-500 bg-red-50",
};

interface NotificationBellProps {
  onNavigate?: ((view: AppView, resourceId?: string) => void) | undefined;
}

export function NotificationBell({ onNavigate }: NotificationBellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { data: unreadCount } = useUnreadCount();
  const { data: notificationsData } = useNotifications({ limit: 15 });
  const markReadMutation = useMarkNotificationRead();
  const markAllMutation = useMarkAllRead();

  useClickOutside(dropdownRef, isOpen, () => setIsOpen(false));

  const notifications = notificationsData?.data ?? [];
  const count = unreadCount ?? 0;

  function handleClick(notification: NotificationItem) {
    if (!notification.is_read) {
      markReadMutation.mutate(notification.id);
    }
    setIsOpen(false);
    if (onNavigate && notification.resource_type) {
      const viewMap: Record<string, AppView> = {
        conversation: "chat",
        risk_entry: "risk-register",
      };
      const view = viewMap[notification.resource_type];
      if (view) {
        onNavigate(view, notification.resource_id ?? undefined);
      }
    }
  }

  function handleMarkAll() {
    markAllMutation.mutate();
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative rounded-xl border border-gray-200 p-2.5 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600"
        aria-label="Notifications"
      >
        <Bell size={18} />
        {count > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-50 mt-2 w-[380px] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
            <span className="text-sm font-bold text-slate-800">Notifications</span>
            {count > 0 && (
              <button
                onClick={handleMarkAll}
                disabled={markAllMutation.isPending}
                className="flex items-center gap-1 text-xs font-medium text-brand-500 hover:text-brand-600"
              >
                <CheckCheck size={12} />
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-[400px] overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="py-10 text-center text-sm text-gray-400">
                No notifications yet
              </div>
            ) : (
              notifications.map((n) => {
                const Icon = TYPE_ICONS[n.type] ?? Bell;
                const iconColor = TYPE_COLORS[n.type] ?? "text-gray-500 bg-gray-50";
                return (
                  <button
                    key={n.id}
                    onClick={() => handleClick(n)}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-50 ${
                      !n.is_read ? "bg-brand-50/30" : ""
                    }`}
                  >
                    <div
                      className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${iconColor}`}
                    >
                      <Icon size={14} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium text-slate-800">
                          {n.title}
                        </span>
                        {!n.is_read && (
                          <span className="h-2 w-2 shrink-0 rounded-full bg-brand-500" />
                        )}
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">
                        {n.body}
                      </p>
                      <span className="mt-1 text-[10px] text-slate-400">
                        {formatDistanceToNow(new Date(n.created_at), {
                          addSuffix: true,
                        })}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
