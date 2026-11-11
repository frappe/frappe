// The builder page mounted with a stubbed canvas and a faked API. Mounted with Vue's own `createApp`.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

const fake = vi.hoisted(() => ({
  getDocument: vi.fn(),
  copyDocument: vi.fn(),
  createDocument: vi.fn(),
  updateDocument: vi.fn(),
  runMethod: vi.fn(),
  toastError: vi.fn(),
  rights: { loading: false, create: true },
}));

vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  getDocument: fake.getDocument,
  copyDocument: fake.copyDocument,
  createDocument: fake.createDocument,
  updateDocument: fake.updateDocument,
  runMethod: fake.runMethod,
}));
vi.mock("@framework/ui/useDocPermissions", () => ({
  useDocPermissions: () => ({
    loading: {
      get value() {
        return fake.rights.loading;
      },
    },
    holds: () => fake.rights.create,
  }),
}));
vi.mock("@framework/ui/AutomationCanvas", () => ({
  AutomationCanvas: defineComponent({
    props: ["nodes", "edges"],
    setup: (props) => () => h("div", { "data-canvas": props.nodes.length }),
  }),
}));
vi.mock("@shell", () => ({
  routeFor: (doctype: string, name?: string) => ({
    name: "flow-test",
    params: { doctype, name },
  }),
  useUnloadGuard: () => {},
}));
vi.mock("frappe-ui", async (importOriginal) => {
  const original = await importOriginal<any>();
  return { ...original, toast: { ...original.toast, error: fake.toastError } };
});

import { ApiError } from "@framework/ui/api";
import FlowBuilder from "../../../frappe/automation/doctype/automation_flow/frontend/FlowBuilder.vue";

const saved = {
  name: "AUTO-00001",
  title: "Notify",
  enabled: 1,
  document_type: "ToDo",
  trigger_type: "Document Created",
  modified: "2026-11-11 10:00:00",
  actions: [
    {
      name: "row-1",
      idx: 1,
      step_type: "Action",
      action_type: "SetFieldValue",
      step_key: "step_1",
      params: "{}",
      parent_step: 0,
      branch: "",
    },
  ],
};

let app: App;
let router: Router;
let host: HTMLElement;

async function mount(name: string | null, query: Record<string, string> = {}) {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/:pathMatch(.*)*",
        name: "flow-test",
        component: { render: () => null },
      },
    ],
  });
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({ render: () => h("div", [h(FlowBuilder, { name, query })]) });
  app.use(router);
  app.mount(host);
  await settle();
}

async function settle() {
  for (let i = 0; i < 6; i++) await nextTick();
  await new Promise((resolve) => setTimeout(resolve));
}

const button = (label: string) =>
  [...host.querySelectorAll("button")].find(
    (b) => b.textContent?.trim() === label
  ) as HTMLElement;
const titleInput = () =>
  host.querySelector("[data-flow-title]") as HTMLInputElement;

async function typeTitle(value: string) {
  const input = titleInput();
  input.value = value;
  input.dispatchEvent(new Event("input"));
  await settle();
}

beforeEach(() => {
  vi.resetAllMocks();
  fake.rights.loading = false;
  fake.rights.create = true;
  fake.runMethod.mockResolvedValue({
    data: { actions: [], trigger_events: [] },
  });
  fake.getDocument.mockResolvedValue({ data: structuredClone(saved) });
});

afterEach(() => {
  app.unmount();
  host.remove();
});

describe("Automation Flow builder", () => {
  it("loads the flow and its steps onto the canvas", async () => {
    await mount("AUTO-00001");

    expect(fake.getDocument).toHaveBeenCalledWith(
      "Automation Flow",
      "AUTO-00001"
    );
    expect(titleInput().value).toBe("Notify");
    expect(
      host.querySelector("[data-canvas]")?.getAttribute("data-canvas")
    ).toBe("2");
    expect(host.textContent).not.toContain("Unsaved");
  });

  it("saves an edit as a PATCH with the title and no unsaved badge after", async () => {
    fake.updateDocument.mockResolvedValue({
      data: { ...structuredClone(saved), title: "Renamed" },
    });
    await mount("AUTO-00001");

    await typeTitle("Renamed");
    expect(host.textContent).toContain("Unsaved");
    button("Save").click();
    await settle();

    const [doctype, name, payload] = fake.updateDocument.mock.calls[0];
    expect([doctype, name, payload.title]).toEqual([
      "Automation Flow",
      "AUTO-00001",
      "Renamed",
    ]);
    expect(host.textContent).not.toContain("Unsaved");
  });

  it("inserts a new flow and then replaces the address with the record", async () => {
    fake.createDocument.mockResolvedValue({
      data: {
        ...structuredClone(saved),
        name: "AUTO-00009",
        title: "Fresh",
        actions: [],
      },
    });
    await mount(null);
    const replace = vi.spyOn(router, "replace");

    expect(host.textContent).toContain("Unsaved");
    await typeTitle("Fresh");
    button("Save").click();
    await settle();

    expect(fake.createDocument).toHaveBeenCalledOnce();
    expect(fake.updateDocument).not.toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith({
      name: "flow-test",
      params: { doctype: "Automation Flow", name: "AUTO-00009" },
    });
  });

  it("refuses to save a flow with no title", async () => {
    await mount(null);

    button("Save").click();
    await settle();

    expect(fake.createDocument).not.toHaveBeenCalled();
    expect(fake.toastError).toHaveBeenCalled();
  });

  it("shows the save conflict when the flow changed since it was opened", async () => {
    fake.updateDocument.mockRejectedValue(
      new ApiError(
        {
          type: "TimestampMismatchError",
          message: "Document has been modified",
        },
        417
      )
    );
    await mount("AUTO-00001");

    await typeTitle("Renamed");
    button("Save").click();
    await settle();

    expect(host.querySelector("[role=alert]")?.textContent).toContain(
      "Someone else saved"
    );
    expect(host.textContent).toContain("Unsaved");
  });

  it("keeps the conflict banner when the reload fails", async () => {
    fake.updateDocument.mockRejectedValue(
      new ApiError(
        {
          type: "TimestampMismatchError",
          message: "Document has been modified",
        },
        417
      )
    );
    await mount("AUTO-00001");
    await typeTitle("Renamed");
    button("Save").click();
    await settle();

    fake.getDocument.mockRejectedValue(
      new ApiError({ type: "ServerError", message: "down" }, 500)
    );
    button("Reload and discard my changes").click();
    await settle();

    expect(host.querySelector("[role=alert]")).not.toBeNull();
    expect(fake.toastError).toHaveBeenCalled();
  });

  it("says who may open it when the server answers 403", async () => {
    fake.getDocument.mockRejectedValue(
      new ApiError({ type: "PermissionError", message: "no" }, 403)
    );
    await mount("AUTO-00001");

    expect(host.textContent).toContain("Not permitted");
    expect(host.textContent).toContain("System Manager");
    expect(host.querySelector("[data-canvas]")).toBeNull();
  });

  describe("a new flow", () => {
    const source = {
      title: "Notify",
      enabled: 1,
      document_type: "ToDo",
      trigger_type: "Document Created",
      actions: saved.actions.map(({ name, ...row }) => row),
    };

    it("opens prefilled from the flow `__copy_of` names, unsaved until the first Save", async () => {
      fake.copyDocument.mockResolvedValue({ data: structuredClone(source) });
      fake.createDocument.mockResolvedValue({
        data: { ...structuredClone(saved), name: "AUTO-00010" },
      });
      await mount(null, { __copy_of: "AUTO-00001" });

      expect(fake.copyDocument).toHaveBeenCalledWith(
        "Automation Flow",
        "AUTO-00001"
      );
      expect(fake.getDocument).not.toHaveBeenCalled();
      expect(titleInput().value).toBe("Notify");
      expect(
        host.querySelector("[data-canvas]")?.getAttribute("data-canvas")
      ).toBe("2");
      expect(host.textContent).toContain("Unsaved");
      expect(fake.createDocument).not.toHaveBeenCalled();

      button("Save").click();
      await settle();

      const [doctype, payload] = fake.createDocument.mock.calls[0];
      expect(doctype).toBe("Automation Flow");
      expect([payload.name, payload.title, payload.actions.length]).toEqual([
        undefined,
        "Notify",
        1,
      ]);
    });

    it("lets the address's values sit over the empty flow", async () => {
      await mount(null, {
        title: "From the dialog",
        document_type: "Lead",
        enabled: "0",
      });

      expect(fake.copyDocument).not.toHaveBeenCalled();
      expect(titleInput().value).toBe("From the dialog");
    });

    it("says the flow was not found when the copied flow is gone", async () => {
      fake.copyDocument.mockRejectedValue(
        new ApiError({ type: "DoesNotExistError", message: "no" }, 404)
      );
      await mount(null, { __copy_of: "AUTO-00404" });

      expect(host.textContent).toContain("Flow not found");
      expect(host.querySelector("[data-canvas]")).toBeNull();
    });

    it("shows the Not permitted state to a person with no create right", async () => {
      fake.rights.create = false;
      await mount(null);

      expect(host.textContent).toContain("Not permitted");
      expect(host.textContent).toContain("System Manager");
      expect(host.querySelector("[data-canvas]")).toBeNull();
      expect(button("Save")).toBeUndefined();
    });

    it("draws no page while the create right is still loading", async () => {
      fake.rights.loading = true;
      await mount(null);

      expect(host.querySelector("[data-canvas]")).toBeNull();
      expect(host.textContent).not.toContain("Not permitted");
    });

    it("does not ask for the create right to open a saved flow", async () => {
      fake.rights.create = false;
      await mount("AUTO-00001");

      expect(host.querySelector("[data-canvas]")).not.toBeNull();
    });
  });
});
