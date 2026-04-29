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
    name: "Preliminary Hazard List",
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
