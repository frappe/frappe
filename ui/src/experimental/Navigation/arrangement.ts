import type { ArrangedRow, NavigationItem, NavigationSection } from "./types";

export function toRows(items: NavigationItem[]): ArrangedRow[] {
  return items.map((item) => ({
    name: item.name,
    hidden: item.hidden ? 1 : 0,
  }));
}

export function toBoxedRows(
  shown: NavigationItem[],
  hidden: NavigationItem[]
): ArrangedRow[] {
  return [
    ...shown.map((item) => ({ name: item.name, hidden: 0 as const })),
    ...hidden.map((item) => ({ name: item.name, hidden: 1 as const })),
  ];
}

export function holdsItem(
  sections: NavigationSection[],
  section: NavigationSection,
  item: NavigationItem
): boolean {
  const stored = sections.find((candidate) => candidate.name === section.name);
  return Boolean(stored?.items.some((candidate) => candidate.name === item.name));
}

export function withHidden(
  items: NavigationItem[],
  name: string,
  hidden: boolean
): ArrangedRow[] {
  return toRows(items).map((row) =>
    row.name === name ? { ...row, hidden: hidden ? 1 : 0 } : row
  );
}

export function flipsVisibility(
  from: NavigationSection,
  to: NavigationSection
): boolean {
  return Boolean(from.user) !== Boolean(to.user);
}

export function findSourceSection(
  sections: NavigationSection[],
  item: NavigationItem,
  destination: NavigationSection
): NavigationSection | undefined {
  return sections.find(
    (section) =>
      section.name !== destination.name &&
      section.items.some((candidate) => candidate.name === item.name)
  );
}

export function canEditSection(
  section: NavigationSection,
  forEveryone: boolean
): boolean {
  return section.user ? true : forEveryone;
}

export function canEditItem(
  section: NavigationSection,
  item: NavigationItem,
  forEveryone: boolean
): boolean {
  return item.own ? true : canEditSection(section, forEveryone);
}
