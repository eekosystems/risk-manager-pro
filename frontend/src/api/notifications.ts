import { apiClient } from "@/lib/api-client";
import type {
  DataResponse,
  NotificationItem,
  PaginatedResponse,
  UnreadCount,
} from "@/types/api";

export async function getNotifications(
  params: { unread_only?: boolean; skip?: number; limit?: number } = {},
): Promise<{ data: NotificationItem[]; total: number }> {
  const response = await apiClient.get<PaginatedResponse<NotificationItem>>(
    "/notifications",
    { params },
  );
  return { data: response.data.data, total: response.data.meta.total };
}

export async function getUnreadCount(): Promise<number> {
  const response = await apiClient.get<DataResponse<UnreadCount>>(
    "/notifications/unread-count",
  );
  return response.data.data.count;
}

export async function markNotificationRead(
  notificationId: string,
): Promise<NotificationItem> {
  const response = await apiClient.patch<DataResponse<NotificationItem>>(
    `/notifications/${notificationId}/read`,
  );
  return response.data.data;
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiClient.post("/notifications/mark-all-read");
}
