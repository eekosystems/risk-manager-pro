import { apiClient } from "@/lib/api-client";
import type { DataResponse, DocumentFolder } from "@/types/api";

export async function getDocumentFolders(): Promise<DocumentFolder[]> {
  const response =
    await apiClient.get<DataResponse<DocumentFolder[]>>("/document-folders");
  return response.data.data;
}

export interface CreateFolderParams {
  name: string;
  parentId?: string | null;
}

export async function createDocumentFolder(
  params: CreateFolderParams,
): Promise<DocumentFolder> {
  const response = await apiClient.post<DataResponse<DocumentFolder>>(
    "/document-folders",
    { name: params.name, parent_id: params.parentId ?? null },
  );
  return response.data.data;
}

export interface RenameFolderParams {
  folderId: string;
  name: string;
}

export async function renameDocumentFolder(
  params: RenameFolderParams,
): Promise<DocumentFolder> {
  const response = await apiClient.patch<DataResponse<DocumentFolder>>(
    `/document-folders/${params.folderId}`,
    { name: params.name },
  );
  return response.data.data;
}

export interface MoveFolderParams {
  folderId: string;
  parentId: string | null;
}

export async function moveDocumentFolder(
  params: MoveFolderParams,
): Promise<DocumentFolder> {
  const response = await apiClient.patch<DataResponse<DocumentFolder>>(
    `/document-folders/${params.folderId}/parent`,
    { parent_id: params.parentId },
  );
  return response.data.data;
}

export async function deleteDocumentFolder(folderId: string): Promise<void> {
  await apiClient.delete(`/document-folders/${folderId}`);
}
