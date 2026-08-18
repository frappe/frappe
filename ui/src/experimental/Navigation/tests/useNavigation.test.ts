import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

const h = vi.hoisted(() => ({
  resource: null as any,
  resourceOptions: null as any,
  sharedResource: null as any,
  sharedOptions: null as any,
  call: null as any,
}));

vi.mock("frappe-ui", async () => {
  const { reactive } = await import("vue");
  h.call = vi.fn(() => Promise.resolve("7"));
  return {
    call: (...args: unknown[]) => h.call(...args),
    createResource: (options: any) => {
      const resource = reactive({
        data: null,
        loading: false,
        error: null,
        fetch: vi.fn(),
      });
      if (options.params?.for_everyone) {
        h.sharedOptions = options;
        h.sharedResource = resource;
      } else {
        h.resourceOptions = options;
        h.resource = resource;
      }
      return resource;
    },
  };
});

import { resetNavigationScopes, useNavigation } from "../useNavigation";
import type {
  NavigationItem,
  NavigationSection,
  SidebarResponse,
} from "../types";

beforeEach(() => {
  resetNavigationScopes();
});

function viewItem(
  name: string,
  label: string,
  hidden: 0 | 1 = 0
): NavigationItem {
  return {
    name: `row${name}`,
    type: "view",
    label,
    icon: "",
    dt: "",
    url: "",
    new_tab: 0,
    hidden,
    own: 0,
    view: { name, label, reference_doctype: "Note", type: "list" },
  };
}

const SECTIONS: NavigationSection[] = [
  {
    name: "s1",
    label: "Views",
    user: "",
    hidden: 0,
    items: [viewItem("1", "Open")],
  },
];

const SIDEBAR: SidebarResponse = {
  sections: SECTIONS,
  can_manage_shared: false,
  default_view: null,
  default_view_is_stored: false,
};

describe("useNavigation", () => {
  beforeEach(() => {
    h.call.mockClear();
  });

  it("exposes the fetched sections", () => {
    const navigation = useNavigation("Note", null);
    h.resource.data = SIDEBAR;

    expect(navigation.sections.value).toEqual(SECTIONS);
  });

  it("has no sections before the fetch resolves", () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.sections.value).toEqual([]);
  });

  it("resolves the active id against the loaded sections", () => {
    const activeId = ref<string | null>(null);
    const navigation = useNavigation("Note", activeId);
    h.resource.data = SIDEBAR;

    expect(navigation.activeView.value).toBeUndefined();

    activeId.value = "1";

    expect(navigation.activeView.value?.label).toBe("Open");
  });

  it("reports whether the session user manages the shared area", () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.canManageShared.value).toBe(false);

    h.resource.data = { ...SIDEBAR, can_manage_shared: true };

    expect(navigation.canManageShared.value).toBe(true);
  });

  it("assumes no shared-area rights before the sections load", () => {
    expect(useNavigation("Note", null).canManageShared.value).toBe(false);
  });

  it("reads the shared arrangement on demand, not with the sections", async () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.sharedSections.value).toEqual([]);
    expect(h.sharedResource.fetch).not.toHaveBeenCalled();

    await navigation.loadShared();

    expect(h.sharedResource.fetch).toHaveBeenCalled();
    expect(h.sharedOptions.params).toMatchObject({
      reference_doctype: "Note",
      for_everyone: true,
    });
  });

  it("keeps the shared arrangement apart from the user's own", () => {
    const navigation = useNavigation("Note", null);
    h.resource.data = SIDEBAR;
    h.sharedResource.data = { ...SIDEBAR, sections: [] };

    expect(navigation.sections.value).toEqual(SECTIONS);
    expect(navigation.sharedSections.value).toEqual([]);
  });

  it("surfaces the server's default view, and null before it loads", () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.defaultView.value).toBe(null);

    h.resource.data = { ...SIDEBAR, default_view: "1" };

    expect(navigation.defaultView.value).toBe("1");
  });

  it("separates a stored default from the stand-in the server fell back to", () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.defaultViewIsStored.value).toBe(false);

    h.resource.data = { ...SIDEBAR, default_view: "1" };
    expect(navigation.defaultView.value).toBe("1");
    expect(navigation.defaultViewIsStored.value).toBe(false);

    h.resource.data = {
      ...SIDEBAR,
      default_view: "1",
      default_view_is_stored: true,
    };
    expect(navigation.defaultViewIsStored.value).toBe(true);
  });
});

describe("useNavigation mutations", () => {
  beforeEach(() => {
    h.call.mockClear();
  });

  function endpointOf(nth = 0) {
    return h.call.mock.calls[nth][0];
  }

  function paramsOf(nth = 0) {
    return h.call.mock.calls[nth][1];
  }

  it("refetches the sections after a mutation", async () => {
    const navigation = useNavigation("Note", null);
    h.resource.fetch.mockClear();

    await navigation.addToSidebar("9");

    expect(h.resource.fetch).toHaveBeenCalled();
  });

  it("adding to the sidebar is a different call than removing", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.addToSidebar("7");
    await navigation.removeFromSidebar("7");

    expect(endpointOf(0)).toContain("add_to_sidebar");
    expect(endpointOf(1)).toContain("remove_from_sidebar");
  });

  it("loads the pool on demand, not with the sections", async () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.pool.value).toEqual([]);
    expect(h.call).not.toHaveBeenCalled();

    h.call.mockResolvedValueOnce([{ name: "9", label: "Unplaced" }]);
    await navigation.loadPool();

    expect(navigation.pool.value).toEqual([{ name: "9", label: "Unplaced" }]);
  });

  it("loads counts on demand, not with the sections", async () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.counts.value).toEqual({});
    expect(h.call).not.toHaveBeenCalled();

    h.call.mockResolvedValueOnce({ "1": 7, "2": null });
    await navigation.loadCounts();

    expect(endpointOf()).toContain("get_view_counts");
    expect(paramsOf()).toMatchObject({ reference_doctype: "Note" });
    expect(navigation.counts.value).toEqual({ "1": 7, "2": null });
  });

  it("refreshes an already-loaded pool after a mutation", async () => {
    const navigation = useNavigation("Note", null);
    h.call.mockResolvedValueOnce([{ name: "9", label: "Unplaced" }]);
    await navigation.loadPool();
    h.call.mockClear();

    h.call.mockResolvedValueOnce("7");
    h.call.mockResolvedValueOnce([]);
    await navigation.addToSidebar("9");

    expect(navigation.pool.value).toEqual([]);
  });

  it("refreshes an already-loaded shared arrangement after a mutation", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.addToSidebar("9");

    expect(h.sharedResource.fetch).not.toHaveBeenCalled();

    h.sharedResource.data = { ...SIDEBAR, sections: [] };
    await navigation.addToSidebar("9");

    expect(h.sharedResource.fetch).toHaveBeenCalled();
  });

  it("arranges a section as the acting user by default", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.arrangeItems("s1", [{ name: "row1", hidden: 0 }]);

    expect(endpointOf()).toContain("arrange_items");
    expect(paramsOf()).toMatchObject({ section: "s1", for_everyone: false });
  });

  it("arranges a section for everyone when a manager says so", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.arrangeItems("s1", [{ name: "row1", hidden: 0 }], true);

    expect(paramsOf()).toMatchObject({ for_everyone: true });
  });

  it("drops a view into another section at an index", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.moveViewToSection("7", "s2", 1);

    expect(endpointOf()).toContain("move_view_to_section");
    expect(paramsOf()).toMatchObject({ view: "7", section: "s2", index: 1 });
  });

  it("renames and deletes a section through stock document calls", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.renameSection("s1", "All deals");
    await navigation.deleteSection("s1");

    expect(endpointOf(0)).toBe("frappe.client.set_value");
    expect(paramsOf(0)).toMatchObject({ doctype: "Navigation Section" });
    expect(endpointOf(1)).toBe("frappe.client.delete");
  });

  it("creates a section for its own doctype", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.createSection("Pipeline", true);

    expect(endpointOf()).toContain("create_section");
    expect(paramsOf()).toMatchObject({
      reference_doctype: "Note",
      label: "Pipeline",
      shared: true,
    });
  });

  it("reorders sections onto the caller's overlays by default", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.arrangeSections(["s2", "s1"]);

    expect(endpointOf()).toContain("arrange_sections");
    expect(paramsOf()).toMatchObject({
      sections: ["s2", "s1"],
      for_everyone: false,
    });
  });

  it("passes a manager's for-everyone section order through", async () => {
    const navigation = useNavigation("Note", null);

    await navigation.arrangeSections(["s2", "s1"], true);

    expect(paramsOf()).toMatchObject({ for_everyone: true });
  });
});

describe("useNavigation app scope", () => {
  beforeEach(() => {
    h.call.mockClear();
  });

  function paramsOf(nth = 0) {
    return h.call.mock.calls[nth][1];
  }

  it("reads only the given app's sections", () => {
    useNavigation("Note", null, { app: "crm" });

    expect(h.resourceOptions.params).toEqual({
      reference_doctype: "Note",
      app: "crm",
    });
  });

  it("falls back to the framework's own app", () => {
    useNavigation("Note", null);

    expect(h.resourceOptions.params).toMatchObject({ app: "frappe" });
  });

  it("exposes the resolved app, which is what a composed useSavedViews takes", () => {
    expect(useNavigation("Note", null).app.value).toBe("frappe");
    expect(useNavigation("Note", null, { app: "crm" }).app.value).toBe("crm");
  });

  it("names the app on every call that has to find or create a section", async () => {
    const navigation = useNavigation("Note", null, { app: "crm" });

    await navigation.createSection("Pipeline", true);
    await navigation.arrangeSections(["s1"]);
    await navigation.addToSidebar("9");
    await navigation.loadCounts();
    await navigation.loadPool();

    for (const nth of [0, 1, 2, 3, 4]) {
      expect(paramsOf(nth)).toMatchObject({ app: "crm" });
    }
  });
});

describe("useNavigation hidden items", () => {
  const WITH_HIDDEN: SidebarResponse = {
    can_manage_shared: false,
    default_view: null,
    default_view_is_stored: false,
    sections: [
      {
        name: "s1",
        label: "Views",
        user: "",
        hidden: 0,
        items: [viewItem("1", "Open"), viewItem("2", "Archived", 1)],
      },
      {
        name: "s2",
        label: "Retired",
        user: "",
        hidden: 1,
        items: [viewItem("3", "Old")],
      },
    ],
  };

  it("sections carries hidden items so edit mode can offer an unhide", () => {
    const navigation = useNavigation("Note", null);
    h.resource.data = WITH_HIDDEN;

    expect(navigation.sections.value[0].items).toHaveLength(2);
  });

  it("visibleSections drops them, which is what the sidebar renders", () => {
    const navigation = useNavigation("Note", null);
    h.resource.data = WITH_HIDDEN;

    expect(
      navigation.visibleSections.value[0].items.map((item) => item.label)
    ).toEqual(["Open"]);
  });

  it("sections carries a hidden section for the same reason", () => {
    const navigation = useNavigation("Note", null);
    h.resource.data = WITH_HIDDEN;

    expect(navigation.sections.value.map((section) => section.name)).toEqual([
      "s1",
      "s2",
    ]);
  });

  it("visibleSections drops a hidden section whole", () => {
    const navigation = useNavigation("Note", null);
    h.resource.data = WITH_HIDDEN;

    expect(
      navigation.visibleSections.value.map((section) => section.name)
    ).toEqual(["s1"]);
  });

  it("a hidden view still resolves when the route names it", () => {
    const navigation = useNavigation("Note", "2");
    h.resource.data = WITH_HIDDEN;

    expect(navigation.activeView.value?.label).toBe("Archived");
  });
});

describe("useNavigation scope sharing", () => {
  beforeEach(() => {
    h.call.mockClear();
  });

  it("caches the sections per app and doctype", () => {
    useNavigation("Task", null, { app: "crm" });

    expect(h.resourceOptions.cache).toEqual([
      "navigation-sidebar",
      "crm",
      "Task",
    ]);
  });

  it("separates the cache of two doctypes in the same app", () => {
    useNavigation("ToDo", null, { app: "crm" });
    const todo = h.resourceOptions.cache;
    useNavigation("Event", null, { app: "crm" });

    expect(h.resourceOptions.cache).not.toEqual(todo);
  });

  it("builds the sections resource once for an app and doctype", () => {
    useNavigation("Contact", null, { app: "crm" });
    const first = h.resource;
    useNavigation("Contact", null, { app: "crm" });

    expect(h.resource).toBe(first);
    expect(first.fetch).toHaveBeenCalledTimes(1);
  });

  it("builds one per app, so two apps do not share a doctype's sections", () => {
    useNavigation("Contact", null, { app: "crm" });
    const crm = h.resource;
    useNavigation("Contact", null, { app: "helpdesk" });

    expect(h.resource).not.toBe(crm);
  });

  it("hands every consumer of a scope the same counts", async () => {
    const sidebar = useNavigation("Contact", null);
    const page = useNavigation("Contact", "1");

    h.call.mockResolvedValueOnce({ "1": 4 });
    await page.loadCounts();

    expect(sidebar.counts.value).toEqual({ "1": 4 });
  });

  it("does not hand one doctype's counts to another", async () => {
    h.call.mockResolvedValueOnce({ "1": 4 });
    await useNavigation("Comment", null).loadCounts();

    expect(useNavigation("File", null).counts.value).toEqual({});
  });

  it("hands every consumer of a scope the same pool", async () => {
    const sidebar = useNavigation("Contact", null);

    h.call.mockResolvedValueOnce([{ name: "9", label: "Unplaced" }]);
    await useNavigation("Contact", "1").loadPool();

    expect(sidebar.pool.value).toEqual([{ name: "9", label: "Unplaced" }]);
  });

  it("reloads the shared sections when one consumer mutates", async () => {
    const sidebar = useNavigation("Contact", null);
    const page = useNavigation("Contact", "1");
    h.resource.fetch.mockClear();

    h.resource.data = SIDEBAR;
    await page.addToSidebar("9");

    expect(h.resource.fetch).toHaveBeenCalled();
    expect(sidebar.sections.value).toEqual(page.sections.value);
  });

  it("resolves each consumer's own active view against the shared sections", () => {
    const sidebar = useNavigation("Note", null);
    const page = useNavigation("Note", "1");
    h.resource.data = SIDEBAR;

    expect(sidebar.activeView.value).toBeUndefined();
    expect(page.activeView.value?.label).toBe("Open");
  });

  it("follows a reactive doctype onto the other scope's sections", () => {
    const doctype = ref("Note");
    const navigation = useNavigation(doctype, null, { app: "crm" });
    const note = h.resource;
    note.data = SIDEBAR;

    expect(navigation.sections.value).toEqual(SECTIONS);

    doctype.value = "Task";

    expect(navigation.sections.value).toEqual([]);
    expect(h.resource).not.toBe(note);
    expect(h.resourceOptions.params).toMatchObject({
      reference_doctype: "Task",
    });
  });

  it("goes back to a scope it already built rather than refetching it", async () => {
    const doctype = ref("Note");
    const navigation = useNavigation(doctype, null, { app: "crm" });
    const note = h.resource;
    note.data = SIDEBAR;

    doctype.value = "Task";
    await nextTick();
    doctype.value = "Note";
    await nextTick();

    expect(navigation.sections.value).toEqual(SECTIONS);
    expect(note.fetch).toHaveBeenCalledTimes(1);
  });

  it("reports fetched so the sidebar can skip its skeleton on a warm load", () => {
    const navigation = useNavigation("Note", null);

    expect(navigation.fetched.value).toBe(false);

    h.resource.fetched = true;

    expect(navigation.fetched.value).toBe(true);
  });
});
