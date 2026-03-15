import { apiClient } from "@/lib/api-client";
import type {
  DataResponse,
  DocumentItem,
  PaginatedResponse,
  SourceType,
} from "@/types/api";

export interface UploadDocumentParams {
  file: File;
  sourceType?: SourceType;
}

export async function uploadDocument(
  params: UploadDocumentParams,
): Promise<DocumentItem> {
  const { file, sourceType = "client" } = params;
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<DataResponse<DocumentItem>>(
    `/documents/upload?source_type=${encodeURIComponent(sourceType)}`,
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
