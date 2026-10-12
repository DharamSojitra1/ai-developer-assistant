import { Calculator, Library, Network } from "lucide-react";
import type { ReactNode } from "react";

import type { AgentRoute } from "@/api/types";
import { Badge } from "@/components/ui/Badge";

/** Only routes that used a tool get a badge; plain answers need none. */
const ROUTES: Partial<Record<AgentRoute, { label: string; description: string; icon: ReactNode }>> = {
  knowledge_base: {
    label: "Knowledge base",
    description: "Answered by searching your knowledge base",
    icon: <Library aria-hidden />,
  },
  calculation: {
    label: "Calculator",
    description: "Answered with the calculator tool",
    icon: <Calculator aria-hidden />,
  },
  multi_agent: {
    label: "Multi-agent",
    description: "Coordinated by the supervisor across several agents",
    icon: <Network aria-hidden />,
  },
};

export function RouteBadge({ route }: { route: AgentRoute }) {
  const config = ROUTES[route];
  if (!config) return null;

  return (
    <span title={config.description}>
      <Badge icon={config.icon}>
        {config.label}
        <span className="sr-only">: {config.description}</span>
      </Badge>
    </span>
  );
}
