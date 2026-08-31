import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DocumentFolder, DocumentItem } from "@/types/api";

import { IndexedFilesTab } from "./indexed-files-tab";

const getDocuments = vi.fn();
const getDocumentFolders = vi.fn();
const getSharePointDrives = vi.fn();
const moveDocuments = vi.fn();
const createDocumentFolder = vi.fn();
const moveDocumentFolder = vi.fn();

vi.mock("@/api/documents", () => ({
  getDocuments: () => getDocuments(),
  getSharePointDrives: () => getSharePointDrives(),
  moveDocuments: (params: unknown) => moveDocuments(params),
  deleteDocument: vi.fn(),
  reindexDocument: vi.fn(),
  processAllDocuments: vi.fn(),
  crawlSharePoint: vi.fn(),
  syncFolder: vi.fn(),
}));

vi.mock("@/api/document-folders", () => ({
  getDocumentFolders: () => getDocumentFolders(),
  createDocumentFolder: (params: unknown) => createDocumentFolder(params),
  renameDocumentFolder: vi.fn(),
  deleteDocumentFolder: vi.fn(),
  moveDocumentFolder: (params: unknown) => moveDocumentFolder(params),
}));

function makeDocument(overrides: Partial<DocumentItem> = {}): DocumentItem {
  return {
    id: "doc-1",
    filename: "hazard-log.pdf",
    folder_path: null,
    folder_id: null,
    content_type: "application/pdf",
    size_bytes: 1024,
    status: "indexed",
    source_type: "client",
    created_at: "2026-08-01T12:00:00Z",
    ...overrides,
  };
}

function makeFolder(overrides: Partial<DocumentFolder> = {}): DocumentFolder {
  return {
    id: "folder-1",
    name: "Working Set",
    parent_id: null,
    created_at: "2026-08-01T12:00:00Z",
    ...overrides,
  };
}

/** jsdom has no real DataTransfer, and the drag handlers read and write it. */
function makeDataTransfer() {
  return {
    effectAllowed: "",
    dropEffect: "",
    setData: vi.fn(),
    getData: vi.fn(() => ""),
  };
}

function renderTab() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <IndexedFilesTab />
    </QueryClientProvider>,
  );
}

/** Find the clickable row for a folder by its label. */
async function folderRow(name: string): Promise<HTMLElement> {
  const label = await screen.findByText(name);
  const row = label.closest("div.flex.items-center");
  if (!row) throw new Error(`No row found for folder "${name}"`);
  return row as HTMLElement;
}

describe("IndexedFilesTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSharePointDrives.mockResolvedValue([]);
    getDocumentFolders.mockResolvedValue([]);
    getDocuments.mockResolvedValue([]);
    moveDocuments.mockResolvedValue({ moved: 1, folder_id: null });
    createDocumentFolder.mockResolvedValue(makeFolder());
    moveDocumentFolder.mockResolvedValue(makeFolder());
  });

  it("lists uploaded documents at the top level when they have no folder", async () => {
    // Front-end uploads never carry a folder_path, so this is the flat pile
    // the folder feature exists to break up.
    getDocuments.mockResolvedValue([makeDocument({ filename: "uploaded.pdf" })]);

    renderTab();

    expect(await screen.findByText("uploaded.pdf")).toBeInTheDocument();
  });

  it("shows user folders alongside the SharePoint hierarchy", async () => {
    getDocumentFolders.mockResolvedValue([makeFolder({ name: "Working Set" })]);
    getDocuments.mockResolvedValue([
      makeDocument({ id: "doc-sp", folder_path: "Airports/PHL" }),
    ]);

    renderTab();

    expect(await screen.findByText("Working Set")).toBeInTheDocument();
    expect(await screen.findByText("Airports")).toBeInTheDocument();
  });

  it("renders an empty folder that holds no documents", async () => {
    getDocumentFolders.mockResolvedValue([makeFolder({ name: "Empty Folder" })]);

    renderTab();

    const row = await folderRow("Empty Folder");
    expect(within(row).getByText("(0)")).toBeInTheDocument();
  });

  it("places a filed document inside its folder", async () => {
    getDocumentFolders.mockResolvedValue([makeFolder({ id: "folder-1" })]);
    getDocuments.mockResolvedValue([
      makeDocument({ filename: "filed.pdf", folder_id: "folder-1" }),
    ]);

    renderTab();

    const row = await folderRow("Working Set");
    expect(within(row).getByText("(1)")).toBeInTheDocument();

    await userEvent.click(within(row).getByRole("button", { name: /Working Set/ }));
    expect(await screen.findByText("filed.pdf")).toBeInTheDocument();
  });

  it("creates a folder from the New Folder button", async () => {
    renderTab();

    await userEvent.click(await screen.findByRole("button", { name: /New Folder/i }));

    const input = screen.getByPlaceholderText("Folder name");
    await userEvent.type(input, "Audits{Enter}");

    await waitFor(() =>
      expect(createDocumentFolder).toHaveBeenCalledWith({
        name: "Audits",
        parentId: null,
      }),
    );
  });

  it("cancels folder creation on Escape without calling the API", async () => {
    renderTab();

    await userEvent.click(await screen.findByRole("button", { name: /New Folder/i }));
    await userEvent.type(screen.getByPlaceholderText("Folder name"), "Scrapped{Escape}");

    await waitFor(() =>
      expect(screen.queryByPlaceholderText("Folder name")).not.toBeInTheDocument(),
    );
    expect(createDocumentFolder).not.toHaveBeenCalled();
  });

  it("files a document into the folder it is dropped on", async () => {
    getDocumentFolders.mockResolvedValue([makeFolder({ id: "folder-1" })]);
    getDocuments.mockResolvedValue([
      makeDocument({ id: "doc-1", filename: "hazard-log.pdf" }),
    ]);

    renderTab();

    const file = await screen.findByText("hazard-log.pdf");
    const fileRow = file.closest("div[draggable]");
    const target = await folderRow("Working Set");
    const dataTransfer = makeDataTransfer();

    fireEvent.dragStart(fileRow as HTMLElement, { dataTransfer });
    fireEvent.dragOver(target, { dataTransfer });
    fireEvent.drop(target, { dataTransfer });

    await waitFor(() =>
      expect(moveDocuments).toHaveBeenCalledWith({
        documentIds: ["doc-1"],
        folderId: "folder-1",
      }),
    );
  });

  it("moves a document back to the top level when dropped on the top-level strip", async () => {
    getDocumentFolders.mockResolvedValue([makeFolder({ id: "folder-1" })]);
    getDocuments.mockResolvedValue([
      makeDocument({ id: "doc-1", filename: "hazard-log.pdf", folder_id: "folder-1" }),
    ]);

    renderTab();

    const row = await folderRow("Working Set");
    await userEvent.click(within(row).getByRole("button", { name: /Working Set/ }));

    const file = await screen.findByText("hazard-log.pdf");
    const fileRow = file.closest("div[draggable]");
    const dataTransfer = makeDataTransfer();

    fireEvent.dragStart(fileRow as HTMLElement, { dataTransfer });

    const strip = await screen.findByText(/Drop here to move .* to the top level/);
    fireEvent.dragOver(strip, { dataTransfer });
    fireEvent.drop(strip, { dataTransfer });

    await waitFor(() =>
      expect(moveDocuments).toHaveBeenCalledWith({
        documentIds: ["doc-1"],
        folderId: null,
      }),
    );
  });

  it("refuses a drop on a SharePoint folder, which has no folder record", async () => {
    getDocuments.mockResolvedValue([
      makeDocument({ id: "doc-1", filename: "hazard-log.pdf" }),
      makeDocument({ id: "doc-sp", filename: "synced.pdf", folder_path: "Airports" }),
    ]);

    renderTab();

    const file = await screen.findByText("hazard-log.pdf");
    const fileRow = file.closest("div[draggable]");
    const target = await folderRow("Airports");
    const dataTransfer = makeDataTransfer();

    fireEvent.dragStart(fileRow as HTMLElement, { dataTransfer });
    fireEvent.dragOver(target, { dataTransfer });
    fireEvent.drop(target, { dataTransfer });

    expect(dataTransfer.dropEffect).toBe("none");
    expect(moveDocuments).not.toHaveBeenCalled();
  });

  it("reparents a folder dropped onto another folder", async () => {
    getDocumentFolders.mockResolvedValue([
      makeFolder({ id: "folder-1", name: "Working Set" }),
      makeFolder({ id: "folder-2", name: "Archive" }),
    ]);

    renderTab();

    const dragged = await folderRow("Working Set");
    const target = await folderRow("Archive");
    const dataTransfer = makeDataTransfer();

    fireEvent.dragStart(dragged, { dataTransfer });
    fireEvent.dragOver(target, { dataTransfer });
    fireEvent.drop(target, { dataTransfer });

    await waitFor(() =>
      expect(moveDocumentFolder).toHaveBeenCalledWith({
        folderId: "folder-1",
        parentId: "folder-2",
      }),
    );
  });

  it("refuses to drop a folder into its own subfolder", async () => {
    getDocumentFolders.mockResolvedValue([
      makeFolder({ id: "parent", name: "Airports" }),
      makeFolder({ id: "child", name: "PHL", parent_id: "parent" }),
    ]);

    renderTab();

    const parentRow = await folderRow("Airports");
    await userEvent.click(within(parentRow).getByRole("button", { name: /Airports/ }));

    const childRow = await folderRow("PHL");
    const dataTransfer = makeDataTransfer();

    fireEvent.dragStart(parentRow, { dataTransfer });
    fireEvent.dragOver(childRow, { dataTransfer });
    fireEvent.drop(childRow, { dataTransfer });

    expect(dataTransfer.dropEffect).toBe("none");
    expect(moveDocumentFolder).not.toHaveBeenCalled();
  });
});
