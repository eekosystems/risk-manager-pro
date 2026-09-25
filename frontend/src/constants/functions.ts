import { AlertTriangle, BarChart3, ClipboardList, Shield } from "lucide-react";

import type { FunctionType } from "@/types/api";

export interface FunctionDefinition {
  id: FunctionType;
  name: string;
  shortName: string;
  title: string;
  description: string;
  icon: typeof AlertTriangle;
}

// Guided root-cause mode is System Analysis with the 5 Whys run as a
// dialogue. It has no sidebar entry of its own: the System Analysis item
// stays highlighted while a conversation is in it.
export const FUNCTION_FAMILY: Record<FunctionType, FunctionType> = {
  phl: "phl",
  sra: "sra",
  system: "system",
  system_guided: "system",
  general: "general",
  risk_register: "risk_register",
};

export const FUNCTION_DISPLAY_NAMES: Record<FunctionType, string> = {
  phl: "Hazard Assessment",
  sra: "Safety Risk Assessment",
  system: "System Analysis",
  system_guided: "Guided Root-Cause Analysis",
  general: "General",
  risk_register: "Hazard Entry",
};

export const FUNCTIONS: FunctionDefinition[] = [
  {
    id: "system",
    name: "System Analysis",
    shortName: "SA",
    title: "System Analysis",
    description: "Analyze system changes and impacts",
    icon: BarChart3,
  },
  {
    id: "phl",
    name: "Hazard Assessment",
    shortName: "PHL",
    title: "PHL Assessment",
    description: "Identify potential hazards from system changes",
    icon: AlertTriangle,
  },
  {
    id: "sra",
    name: "Safety Risk Assessment",
    shortName: "SRA",
    title: "Risk Assessment",
    description: "Comprehensive risk evaluation and mitigation",
    icon: Shield,
  },
  {
    id: "risk_register",
    name: "Hazard Entry",
    shortName: "Hazard",
    title: "Hazard Entry",
    description: "Conversational hazard entry into the Airport Risk Register",
    icon: ClipboardList,
  },
];
