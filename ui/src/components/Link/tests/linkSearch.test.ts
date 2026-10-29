// A Link field asks the server only when a person opens, focuses or types in it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, reactive } from "vue";
import type { App } from "vue";

const api = vi.hoisted(() => ({ searchDocuments: vi.fn() }));

vi.mock("../../../api", () => ({ searchDocuments: api.searchDocuments }));

import Link from "../Link.vue";

const apps: App[] = [];

beforeEach(() => {
  api.searchDocuments.mockReset();
  api.searchDocuments.mockResolvedValue({ data: [{ value: "Administrator", label: "Administrator" }] });
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

const pastDebounce = () => new Promise((resolve) => setTimeout(resolve, 350));

function searchedTexts(): string[] {
  return api.searchDocuments.mock.calls.map(([, query]) => query.txt);
}

async function mountLink(props: Record<string, unknown> = {}) {
  const state = reactive({
    doctype: "User",
    filters: {} as Record<string, unknown>,
    modelValue: "Administrator" as string | null,
    open: false,
    ...props,
  });
  const host = document.createElement("div");
  document.body.appendChild(host);
  const app = createApp({
    render: () =>
      h(Link, {
        ...state,
        title: "Administrator",
        "onUpdate:modelValue": (value: string | null) => (state.modelValue = value),
        "onUpdate:open": (value: boolean) => (state.open = value),
      }),
  });
  app.mount(host);
  apps.push(app);
  await nextTick();
  return { state, input: host.querySelector<HTMLInputElement>("input")! };
}

describe("Link search", () => {
  it("sends no search at mount, nor for the value the field shows", async () => {
    const { input } = await mountLink();
    await pastDebounce();
    expect(input.value).toBe("Administrator");
    expect(api.searchDocuments).not.toHaveBeenCalled();
  });

  it("searches once when the picker opens after a focus", async () => {
    const { state, input } = await mountLink();
    input.dispatchEvent(new FocusEvent("focus"));
    state.open = true;
    await nextTick();
    await pastDebounce();
    expect(searchedTexts()).toEqual([""]);
  });

  it("searches the text a person types", async () => {
    const { input } = await mountLink({ modelValue: null });
    input.value = "adm";
    input.dispatchEvent(new Event("input"));
    await pastDebounce();
    expect(searchedTexts()).toEqual(["", "adm"]);
  });

  it("sends nothing when a picked value fills the input", async () => {
    const { state, input } = await mountLink({ modelValue: null });
    state.open = true;
    await nextTick();
    await vi.waitFor(() => expect(document.querySelector("[role=option]")).not.toBeNull());
    state.modelValue = "Administrator";
    state.open = false;
    await nextTick();
    await pastDebounce();
    expect(input.value).toBe("Administrator");
    expect(searchedTexts()).toEqual([""]);
  });

  it("searches again on the next open or focus after a doctype or filter change", async () => {
    const { state, input } = await mountLink();
    state.open = true;
    await nextTick();
    state.open = false;
    await nextTick();
    state.open = true;
    await nextTick();
    await pastDebounce();
    expect(searchedTexts()).toEqual([""]);

    state.open = false;
    state.filters = { enabled: 1 };
    await nextTick();
    await pastDebounce();
    expect(api.searchDocuments).toHaveBeenCalledTimes(1);
    state.open = true;
    await nextTick();
    expect(api.searchDocuments).toHaveBeenCalledTimes(2);
    expect(api.searchDocuments.mock.calls[1][1].filters).toEqual({ enabled: 1 });

    state.open = false;
    state.doctype = "Role";
    await nextTick();
    input.dispatchEvent(new FocusEvent("focus"));
    expect(api.searchDocuments.mock.calls.map(([doctype]) => doctype)).toEqual(["User", "User", "Role"]);
  });

  it("searches again on the next open once the answer is a minute old", async () => {
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    const { state } = await mountLink();
    state.open = true;
    await nextTick();
    state.open = false;
    await nextTick();
    now.mockReturnValue(1_000_000 + 61_000);
    state.open = true;
    await nextTick();
    now.mockRestore();
    expect(searchedTexts()).toEqual(["", ""]);
  });

  it("searches again on the next open after a failed search", async () => {
    api.searchDocuments.mockRejectedValueOnce(new Error("offline"));
    const { state } = await mountLink();
    state.open = true;
    await nextTick();
    await vi.waitFor(() => expect(api.searchDocuments).toHaveBeenCalledTimes(1));
    await new Promise((resolve) => setTimeout(resolve));
    state.open = false;
    await nextTick();
    state.open = true;
    await nextTick();
    expect(api.searchDocuments).toHaveBeenCalledTimes(2);
  });

  it("searches at once when the doctype changes while the picker is open", async () => {
    const { state } = await mountLink({ open: true });
    await nextTick();
    state.doctype = "Role";
    await nextTick();
    await pastDebounce();
    expect(api.searchDocuments.mock.calls.map(([doctype]) => doctype)).toEqual(["User", "Role"]);
  });
});
