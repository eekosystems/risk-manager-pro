import { createContext } from "react";

export interface ToastContextValue {
  addToast: (message: string, variant?: "success" | "error" | "warning" | "info") => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);
