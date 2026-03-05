import { apiClient } from "@/lib/api-client";
import type {
  DataResponse,
  DocumentItem,
  PaginatedResponse,
} from "@/types/api";

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<DataResponse<DocumentItem>>(
    "/documents/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return response.data.data;
}

export async function getDocuments(): Promise<DocumentItem[]> {
  const response =
    await apiClient.get<PaginatedResponse<DocumentItem>>("/documents");
  return response.data.data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`);
}
