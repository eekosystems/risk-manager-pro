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
    await apiClient.get<PaginatedResponse<DocumentItem>>("/documents?limit=500");
  return response.data.data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`);
}

export async function reindexDocument(documentId: string): Promise<DocumentItem> {
  const response = await apiClient.post<DataResponse<DocumentItem>>(
    `/documents/${documentId}/reindex`,
  );
  return response.data.data;
}

export interface ProcessAllResult {
  queued: number;
  already_indexed: number;
}

export async function processAllDocuments(): Promise<ProcessAllResult> {
  const response = await apiClient.post<DataResponse<ProcessAllResult>>(
    "/documents/process-all",
  );
  return response.data.data;
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

export interface SyncFolderResult {
  folder_path: string;
  files_found: number;
  files_updated: number;
  files_new: number;
}

export async function syncFolder(
  folderPath: string,
  sourceType?: SourceType,
): Promise<SyncFolderResult> {
  const queryParts = [`folder_path=${encodeURIComponent(folderPath)}`];
  if (sourceType) queryParts.push(`source_type=${encodeURIComponent(sourceType)}`);
  const response = await apiClient.post<DataResponse<SyncFolderResult>>(
    `/sharepoint/sync-folder?${queryParts.join("&")}`,
    undefined,
    { timeout: 300_000 },
  );
  return response.data.data;
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
    undefined,
    { timeout: 300_000 },
  );
  return response.data.data;
}
