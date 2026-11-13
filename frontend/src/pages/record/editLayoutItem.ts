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
