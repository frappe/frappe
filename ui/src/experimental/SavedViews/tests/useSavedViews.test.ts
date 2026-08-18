import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { RawMetaField } from "../../../components/FormLayout/types";
import type { SavedView } from "../types";

const h = vi.hoisted(() => ({
  meta: null as any,
  call: null as any,
}));

vi.mock("../../../composables/useDoctypeMeta", async () => {
  const { ref } = await import("vue");
  h.meta = ref(null);
  return { useDoctypeMeta: () => ({ meta: h.meta }) };
});

vi.mock("frappe-ui", async () => {
  h.call = vi.fn(() => Promise.resolve("7"));
  return { call: (...args: unknown[]) => h.call(...args) };
});

import { useSavedViews } from "../useSavedViews";

const FIELDS: RawMetaField[] = [
  {
    fieldname: "status",
    fieldtype: "Select",
    label: "Status",
    options: "Open\nClosed",
    in_standard_filter: 1,
  },
];

const APP = "crm";

const OPEN: SavedView = {
  name: "1",
  label: "Open",
  reference_doctype: "Note",
  type: "list",
  filters: '[["status", "=", "Open"]]',
  order_by: "modified desc",
};

describe("useSavedViews", () => {
  beforeEach(() => {
    h.meta.value = { name: "Note", fields: FIELDS };
    h.call.mockClear();
  });

  it("snapshots the view the host has open", () => {
    const active = ref<SavedView | null>(null);
    const views = useSavedViews("Note", { app: APP, activeView: active });

    expect(views.activeSnapshot.value).toEqual({});

    active.value = OPEN;

    expect(views.activeSnapshot.value.sort).toEqual([
      { fieldname: "modified", direction: "desc" },
    ]);
    expect(views.activeSnapshot.value.filters).toHaveLength(1);
  });

  it("has an empty snapshot when the host names no view", () => {
    expect(useSavedViews("Note", { app: APP }).activeSnapshot.value).toEqual(
      {}
    );
  });

  it("yields an empty snapshot until meta lands, since conditions need field Meta", () => {
    h.meta.value = null;
    const views = useSavedViews("Note", { app: APP, activeView: OPEN });

    expect(views.activeSnapshot.value.filters).toEqual([]);
  });

  it("applyTo restores into a list view and follows later view changes", () => {
    const active = ref<SavedView | null>(null);
    const views = useSavedViews("Note", { app: APP, activeView: active });
    const listView = { restore: vi.fn() } as any;

    views.applyTo(listView);
    expect(listView.restore).toHaveBeenCalledWith({});

    active.value = OPEN;
    return Promise.resolve().then(() => {
      const last = listView.restore.mock.lastCall?.[0];
      expect(last.sort).toEqual([{ fieldname: "modified", direction: "desc" }]);
    });
  });

  it("applyTo returns a stop handle", () => {
    const active = ref<SavedView | null>(null);
    const views = useSavedViews("Note", { app: APP, activeView: active });
    const listView = { restore: vi.fn() } as any;

    const stop = views.applyTo(listView);
    stop();
    active.value = OPEN;

    return Promise.resolve().then(() => {
      expect(listView.restore).toHaveBeenCalledTimes(1);
    });
  });
});

describe("useSavedViews mutations", () => {
  beforeEach(() => {
    h.meta.value = { name: "Note", fields: FIELDS };
    h.call.mockClear();
  });

  function endpointOf(nth = 0) {
    return h.call.mock.calls[nth][0];
  }

  function paramsOf(nth = 0) {
    return h.call.mock.calls[nth][1];
  }

  it("creates a view for its own doctype", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.createView({ label: "Mine", shared: false });

    expect(endpointOf()).toContain("create_view");
    expect(paramsOf()).toMatchObject({
      reference_doctype: "Note",
      label: "Mine",
      shared: false,
    });
  });

  it("names the host's app on every call that places what it creates", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.createView({ label: "Mine" });
    await views.duplicateView("7");
    await views.moveView("7", true);

    for (const nth of [0, 1, 2]) {
      expect(paramsOf(nth)).toMatchObject({ app: APP });
    }
  });

  it("tells the host to refetch after a mutation, since each one moves a view", async () => {
    const onChange = vi.fn();
    const views = useSavedViews("Note", { app: APP, onChange });

    await views.createView({ label: "Mine" });

    expect(onChange).toHaveBeenCalled();
  });

  it("mutates without a host to notify", async () => {
    await expect(
      useSavedViews("Note", { app: APP }).createView({ label: "Mine" })
    ).resolves.toBe("7");
  });

  it("edits label and icon through the stock field write", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.updateView("7", { label: "Renamed" });

    expect(endpointOf()).toBe("frappe.client.set_value");
    expect(paramsOf()).toMatchObject({
      doctype: "Saved View",
      name: "7",
      fieldname: { label: "Renamed" },
    });
  });

  it("saves the live state into an existing view", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.saveView("7", {
      sort: [{ fieldname: "modified", direction: "desc" }],
    });

    expect(endpointOf()).toContain("save_view_state");
    expect(paramsOf()).toMatchObject({ view: "7", order_by: "modified desc" });
  });

  it("saves a new personal view seeded from the live state", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.saveAsNew(
      { sort: [{ fieldname: "name", direction: "asc" }] },
      { label: "Mine" }
    );

    expect(endpointOf()).toContain("create_view");
    expect(paramsOf()).toMatchObject({
      reference_doctype: "Note",
      label: "Mine",
      order_by: "name asc",
    });
  });

  it("auto-saves the landing state into the caller's default", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.saveLanding({
      sort: [{ fieldname: "name", direction: "asc" }],
    });

    expect(endpointOf()).toContain("save_landing_state");
    expect(paramsOf()).toMatchObject({
      reference_doctype: "Note",
      order_by: "name asc",
    });
  });

  it("surfaces the landing default as a reactive snapshot once loaded", async () => {
    const views = useSavedViews("Note", { app: APP });
    expect(views.landingLoaded.value).toBe(false);
    h.call.mockResolvedValueOnce({
      name: "3",
      label: "Default",
      order_by: "creation asc",
    });

    await views.loadLanding();

    expect(views.landingLoaded.value).toBe(true);
    expect(views.landingSnapshot.value.sort).toEqual([
      { fieldname: "creation", direction: "asc" },
    ]);
  });

  it("has an empty landing snapshot when the caller has no default", async () => {
    const views = useSavedViews("Note", { app: APP });
    h.call.mockResolvedValueOnce(null);

    await views.loadLanding();

    expect(views.landingLoaded.value).toBe(true);
    expect(views.landingSnapshot.value).toEqual({});
  });

  it("moves a view across the shared boundary", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.moveView("7", true);

    expect(endpointOf()).toContain("move_view");
    expect(paramsOf()).toMatchObject({ view: "7", shared: true });
  });

  it("deletes a view", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.deleteView("7");

    expect(endpointOf()).toContain("delete_view");
  });

  it("marks a view as the caller's default", async () => {
    const views = useSavedViews("Note", { app: APP });

    await views.setAsDefault("7");

    expect(endpointOf()).toContain("set_as_default");
  });
});
