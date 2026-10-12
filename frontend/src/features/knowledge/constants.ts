import type { Visibility } from "@/api/types";

export const VISIBILITY_OPTIONS: { value: Visibility; label: string }[] = [
  { value: "private", label: "Private (only you)" },
  { value: "shared", label: "Shared (admins only)" },
];

export const DOC_TYPE_LABELS: Record<string, string> = {
  text: "Text",
  markdown: "Markdown",
  pdf: "PDF",
};
