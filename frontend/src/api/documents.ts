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

// SharePoint

export interface SharePointDrive {
  id: string;
  name: string;
  web_url: string;
}

export interface SharePointCrawlResult {
  files_discovered: number;
  files_queued: number;
  skipped_files: string[];
}

export interface CrawlSharePointParams {
  driveName?: string;
  sourceType?: SourceType;
}

export async function getSharePointDrives(): Promise<SharePointDrive[]> {
  const response = await apiClient.get<DataResponse<{ drives: SharePointDrive[] }>>(
    "/sharepoint/drives",
  );
  return response.data.data.drives;
}

export async function crawlSharePoint(
  params: CrawlSharePointParams = {},
): Promise<SharePointCrawlResult> {
  const queryParts: string[] = [];
  if (params.driveName) queryParts.push(`drive_name=${encodeURIComponent(params.driveName)}`);
  if (params.sourceType) queryParts.push(`source_type=${encodeURIComponent(params.sourceType)}`);
  const query = queryParts.length > 0 ? `?${queryParts.join("&")}` : "";

  const response = await apiClient.post<DataResponse<SharePointCrawlResult>>(
    `/sharepoint/crawl${query}`,
  );
  return response.data.data;
}
