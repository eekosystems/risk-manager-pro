import { AlertTriangle, BarChart3, Shield } from "lucide-react";

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
    description: "Evaluate and mitigate safety risks",
    icon: Shield,
  },
  {
    id: "system",
    name: "System Analysis",
    shortName: "SA",
    title: "System Analysis",
    description: "Analyze system changes and impacts",
    icon: BarChart3,
  },
];
