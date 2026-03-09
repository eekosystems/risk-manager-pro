import { useCallback, useState } from "react";

import { useToast } from "@/hooks/use-toast";
import { validateFiles, type ValidatedFile } from "@/lib/file-validation";

export function useFileUpload() {
  const [files, setFiles] = useState<ValidatedFile[]>([]);
  const { addToast } = useToast();

  const addFiles = useCallback(
    (fileList: FileList) => {
      const { valid, errors } = validateFiles(fileList);
      for (const msg of errors) {
        addToast(msg, "warning");
      }
      if (valid.length > 0) {
        setFiles((prev) => [...prev, ...valid]);
      }
    },
    [addToast],
  );

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
  }, []);

  return { files, addFiles, removeFile, clearFiles };
}
