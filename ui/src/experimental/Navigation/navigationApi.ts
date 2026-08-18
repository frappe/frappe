import { call } from "frappe-ui";
import type {
  ArrangedRow,
  NavigationItemNaming,
  NavigationItemValues,
  NavigationScope,
  PoolView,
  ViewCounts,
} from "./types";
import type { ViewName } from "../SavedViews/savedViewApi";

const SECTION_ENDPOINT = "frappe.desk.doctype.navigation_section.";
const PLACEMENT_ENDPOINT = "frappe.desk.doctype.saved_view.api.";

export const navigationApi = {
  getCounts(scope: NavigationScope, refresh = false): Promise<ViewCounts> {
    return call(SECTION_ENDPOINT + "navigation_section.get_view_counts", {
      ...wire(scope),
      refresh,
    });
  },

  getPool(scope: NavigationScope): Promise<PoolView[]> {
    return call(PLACEMENT_ENDPOINT + "get_pool", wire(scope));
  },

  addToSidebar(view: ViewName, app: string): Promise<ViewName> {
    return call(PLACEMENT_ENDPOINT + "add_to_sidebar", { view, app });
  },

  removeFromSidebar(view: ViewName): Promise<ViewName> {
    return call(PLACEMENT_ENDPOINT + "remove_from_sidebar", { view });
  },

  arrangeItems(section: string, items: ArrangedRow[], forEveryone = false) {
    return call(SECTION_ENDPOINT + "api.arrange_items", {
      section,
      items,
      for_everyone: forEveryone,
    });
  },

  addItem(
    section: string,
    item: NavigationItemValues,
    forEveryone = false
  ): Promise<string> {
    return call(SECTION_ENDPOINT + "api.add_item", {
      section,
      item,
      for_everyone: forEveryone,
    });
  },

  getItem(section: string, item: string): Promise<NavigationItemValues> {
    return call(SECTION_ENDPOINT + "api.get_item", { section, item });
  },

  updateItem(
    section: string,
    item: string,
    naming: NavigationItemNaming,
    forEveryone = false,
    values?: NavigationItemValues
  ) {
    return call(SECTION_ENDPOINT + "api.update_item", {
      section,
      item,
      ...naming,
      for_everyone: forEveryone,
      values,
    });
  },

  removeItem(section: string, item: string) {
    return call(SECTION_ENDPOINT + "api.remove_item", { section, item });
  },

  moveItemToSection(
    source: string,
    item: string,
    section: string,
    index?: number,
    forEveryone = false
  ): Promise<string> {
    return call(SECTION_ENDPOINT + "api.move_item_to_section", {
      source,
      item,
      section,
      index,
      for_everyone: forEveryone,
    });
  },

  moveToSection(
    view: ViewName,
    section: string,
    index?: number
  ): Promise<ViewName> {
    return call(SECTION_ENDPOINT + "api.move_view_to_section", {
      view,
      section,
      index,
    });
  },

  createSection(
    scope: NavigationScope,
    label: string,
    shared = false
  ): Promise<string> {
    return call(SECTION_ENDPOINT + "api.create_section", {
      ...wire(scope),
      label,
      shared,
    });
  },

  hideSection(section: string, hidden: boolean) {
    return call(SECTION_ENDPOINT + "api.hide_section", { section, hidden });
  },

  renameSection(section: string, label: string) {
    return call("frappe.client.set_value", {
      doctype: "Navigation Section",
      name: section,
      fieldname: { label },
    });
  },

  deleteSection(section: string) {
    return call("frappe.client.delete", {
      doctype: "Navigation Section",
      name: section,
    });
  },

  arrangeSections(
    scope: NavigationScope,
    sections: string[],
    forEveryone = false
  ) {
    return call(SECTION_ENDPOINT + "api.arrange_sections", {
      ...wire(scope),
      sections,
      for_everyone: forEveryone,
    });
  },
};

function wire(scope: NavigationScope) {
  return { app: scope.app, reference_doctype: scope.doctype };
}
