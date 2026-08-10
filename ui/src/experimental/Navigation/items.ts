import type { NavigationItem } from "./types";

export type ItemTarget = { path: string } | { leave: string };

export function isViewItem(item: NavigationItem): boolean {
  return item.type === "view";
}

export function isAbsoluteUrl(url: string): boolean {
  return /^[a-z][a-z\d+\-.]*:\/\//i.test(url);
}

export function itemTarget(item: NavigationItem): ItemTarget {
  if (item.new_tab || isAbsoluteUrl(item.url)) return { leave: item.url };
  return { path: item.url };
}
