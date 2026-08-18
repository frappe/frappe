import type { NavigationItemValues } from "./types";

export interface NavigationItemKind {
  type: string;
  label: string;
  icon: string;
  field: string;
  doctype?: string;
  filters?: Record<string, unknown>;
  placeholder?: string;
}

export const BUILT_IN_KINDS: NavigationItemKind[] = [
  {
    type: "link",
    label: "Link",
    icon: "link",
    field: "url",
    placeholder: "https://example.com, /notes, or #settings/general",
  },
  {
    type: "doctype",
    label: "List",
    icon: "list",
    field: "dt",
    doctype: "DocType",
    placeholder: "Pick a doctype",
  },
];

export interface NavigationItemFormValues {
  target: string;
  label: string;
  icon: string;
}

export function addableKinds(
  hostKinds: NavigationItemKind[] = []
): NavigationItemKind[] {
  return [...BUILT_IN_KINDS, ...hostKinds];
}

export function kindMenuOptions(
  hostKinds: NavigationItemKind[] | undefined,
  onPick: (kind: NavigationItemKind) => void
) {
  return addableKinds(hostKinds).map((kind) => ({
    label: kind.label,
    icon: kind.icon,
    onClick: () => onPick(kind),
  }));
}

export function itemValues(
  kind: NavigationItemKind,
  values: NavigationItemFormValues
): NavigationItemValues {
  return {
    type: kind.type,
    label: values.label,
    icon: values.icon,
    [kind.field]: values.target,
  };
}
