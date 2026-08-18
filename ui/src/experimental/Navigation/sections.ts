import { isViewItem } from "./items";
import type { NavigationSection } from "./types";
import type { SavedView } from "../SavedViews/types";

export function findView(
  sections: NavigationSection[],
  id: string | number | null | undefined
): SavedView | undefined {
  if (id === null || id === undefined || id === "") return undefined;
  const wanted = String(id);
  for (const section of sections) {
    const match = section.items.find(
      (item) => item.view && String(item.view.name) === wanted
    );
    if (match?.view) return match.view;
  }
  return undefined;
}

export function isExtrasSection(section: NavigationSection): boolean {
  return !section.items.some(isViewItem);
}

export function findExtrasSection(
  sections: NavigationSection[],
  forEveryone: boolean
): NavigationSection | undefined {
  const candidates = sections.filter(
    (section) => Boolean(section.user) !== forEveryone && isExtrasSection(section)
  );
  return candidates.find((section) => section.items.length) ?? candidates[0];
}

export function findFlatSection(
  sections: NavigationSection[],
  forEveryone: boolean
): NavigationSection | undefined {
  const candidates = forEveryone
    ? sections.filter((section) => !section.user)
    : sections;
  return candidates[candidates.length - 1];
}

export function withExtrasLast(
  sections: NavigationSection[]
): NavigationSection[] {
  const views = sections.filter((section) => !isExtrasSection(section));
  return [...views, ...sections.filter(isExtrasSection)];
}
