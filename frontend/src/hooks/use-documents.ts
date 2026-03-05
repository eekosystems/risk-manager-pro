import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteDocument, getDocuments, uploadDocument } from "@/api/documents";
import { useOrganizationContext } from "@/context/organization-context";

export function useDocuments() {
  const { activeOrganization } = useOrganizationContext();

  return useQuery({
    queryKey: ["documents", activeOrganization?.id],
    queryFn: getDocuments,
    enabled: !!activeOrganization,
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  const { activeOrganization } = useOrganizationContext();

  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["documents", activeOrganization?.id],
      });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  const { activeOrganization } = useOrganizationContext();

  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["documents", activeOrganization?.id],
      });
    },
  });
}
