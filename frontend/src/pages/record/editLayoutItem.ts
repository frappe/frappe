import type { RouteLocationRaw } from "vue-router";
import { __ } from "@/i18n";
import type { HeaderItem } from "@/recordPage";

/** The `⋯` row that opens the DocType editor at `route`, in the editor entries' band. */
export function editLayoutItem(route: RouteLocationRaw): HeaderItem {
  return {
    name: "edit_layout",
    label: __("Edit layout"),
    icon: "lucide-layout-template",
    group: "customize",
    run: (page) => page.router.push(route),
  };
}

/** The editor's route at each layout; null where the editor cannot open it. */
export interface LayoutRoutes {
  details: RouteLocationRaw | null;
  sidePanel: RouteLocationRaw | null;
  quickEntry: RouteLocationRaw | null;
  newRecord: RouteLocationRaw | null;
}

// The names and icons the editor's own layout menu gives each layout.
const LAYOUTS: { key: keyof LayoutRoutes; name: string; label: () => string; icon: string }[] = [
  { key: "details", name: "details", label: () => __("Details"), icon: "lucide-file-text" },
  { key: "sidePanel", name: "side_panel", label: () => __("Side panel"), icon: "lucide-panel-right" },
  { key: "quickEntry", name: "quick_entry", label: () => __("Quick entry"), icon: "lucide-app-window" },
  { key: "newRecord", name: "new_record", label: () => __("New record"), icon: "lucide-file-plus" },
];

/** The `⋯` submenu that opens the editor at each layout; its rows stay out of the palette, where "New record" alone misleads. */
export function editLayoutMenu(routes: LayoutRoutes): HeaderItem[] {
  const rows: HeaderItem[] = [];
  for (const { key, name, label, icon } of LAYOUTS) {
    const route = routes[key];
    if (!route) continue;
    rows.push({
      name: `edit_layout_${name}`,
      label: label(),
      icon,
      group: "edit_layout",
      palette: false,
      run: (page) => page.router.push(route),
    });
  }
  if (!rows.length) return [];
  const menu: HeaderItem = { name: "edit_layout", label: __("Edit layout"), icon: "lucide-layout-template", group: "customize", display: "dropdown" };
  return [menu, ...rows];
}
