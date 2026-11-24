// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

const api = vi.hoisted(() => ({ call: vi.fn(), danger: vi.fn() }));
vi.mock("frappe-ui", () => ({
  call: api.call,
  dialog: { danger: api.danger },
  toast: { success: vi.fn(), error: vi.fn() },
  Badge: { render: () => h("span", "Unsaved") },
  Breadcrumbs: { render: () => h("div") },
  Switch: { render: () => h("div") },
  Button: defineComponent({
    props: ["label", "loading", "disabled"],
    emits: ["click"],
    setup:
      (props, { emit }) =>
      () =>
        h(
          "button",
          {
            disabled: props.loading || props.disabled,
            onClick: () => emit("click"),
          },
          props.label
        ),
  }),
  TextInput: defineComponent({
    props: ["modelValue"],
    emits: ["update:modelValue"],
    setup:
      (props, { emit }) =>
      () =>
        h("input", {
          value: props.modelValue,
          onInput: (event) => emit("update:modelValue", event.target.value),
        }),
  }),
  TabButtons: defineComponent({
    props: ["options", "modelValue"],
    emits: ["update:modelValue"],
    setup:
      (props, { emit }) =>
      () =>
        props.options.map((option) =>
          h(
            "button",
            { onClick: () => emit("update:modelValue", option.value) },
            option.label
          )
        ),
  }),
}));
vi.mock("../capabilities", () => ({
  aliasTargets: () => [],
  loadCapabilities: vi.fn(),
  stepParams: (row) => JSON.parse(row.params),
}));
vi.mock("../graph", () => ({
  workflowNodes: () => [],
  workflowEdges: () => [],
}));
vi.mock("../blocks", () => ({
  blockGroups: () => [
    {
      options: [
        {
          value: "Wait",
          values: { step_type: "Wait", params: '{"unit":"Minutes","value":1}' },
        },
      ],
    },
  ],
}));
vi.mock("../triggers", () => ({
  triggerGroups: () => [],
  triggerFromValue: () => ({}),
}));
vi.mock("../AutomationInspector.vue", () => ({
  default: defineComponent({
    props: ["doc"],
    emits: ["update"],
    setup:
      (props, { emit }) =>
      () =>
        h("div", [
          h(
            "button",
            {
              onClick: () =>
                emit("update", { actions: props.doc.actions.slice(1) }),
            },
            "Remove first step"
          ),
          h(
            "button",
            {
              onClick: () => {
                props.doc.actions[0].step_key = "renamed_wait";
              },
            },
            "Rename first step"
          ),
        ]),
  }),
}));
vi.mock("../../AutomationCanvas/AutomationCanvas.vue", () => ({
  default: defineComponent({
    emits: ["add-node"],
    setup:
      (_props, { emit }) =>
      () =>
        h(
          "button",
          {
            onClick: () => emit("add-node", { value: "Wait" }),
          },
          "Add wait"
        ),
  }),
}));
vi.mock("../AutomationTrialRun.vue", () => ({
  default: {
    props: ["automationName"],
    setup: (props) => () => h("output", props.automationName),
  },
}));
import Builder from "../AutomationBuilder.vue";

const cleanup = [];
afterEach(() => {
  cleanup.splice(0).forEach((stop) => stop());
  vi.resetAllMocks();
});

function mountBuilder() {
  const element = document.createElement("div");
  document.body.append(element);
  const dirty = vi.fn();
  const app = createApp(Builder, { doctype: "ToDo", "onUpdate:dirty": dirty });
  app.mount(element);
  cleanup.push(() => {
    app.unmount();
    element.remove();
  });
  return { element, dirty };
}

async function settle() {
  await Promise.resolve();
  await nextTick();
  await Promise.resolve();
  await nextTick();
}

async function title(element, value) {
  const input = element.querySelector("input");
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
}

function click(element, label) {
  const button = [...element.querySelectorAll("button")].find(
    (node) =>
      node.textContent === label || node.getAttribute("aria-label") === label
  );
  expect(button).toBeTruthy();
  button.click();
}

function saved(request, name = "AUTO-1") {
  return {
    ...request,
    name,
    creation: "T0",
    owner: "user@example.com",
    modified: "T1",
  };
}

describe("automation saves", () => {
  it("updates an inserted flow and enables trials without a parent prop change", async () => {
    api.call.mockImplementation(async (_method, { doc }) => saved(doc));
    const { element } = mountBuilder();
    await title(element, "First");
    click(element, "Save");
    await settle();
    expect(api.call.mock.calls[0][0]).toBe("frappe.client.insert");
    await title(element, "Second");
    click(element, "Save");
    await settle();
    expect(api.call.mock.calls[1][0]).toBe("frappe.client.save");
    expect(api.call.mock.calls[1][1].doc.name).toBe("AUTO-1");
    click(element, "Test Run");
    await nextTick();
    expect(element.querySelector("output")?.textContent).toBe("AUTO-1");
  });

  it("keeps edits made during a save dirty and warns before closing", async () => {
    let finish;
    api.call.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    );
    const { element, dirty } = mountBuilder();
    await title(element, "Submitted");
    click(element, "Save");
    await title(element, "Unsubmitted");
    finish(saved(api.call.mock.calls[0][1].doc));
    await settle();
    expect(dirty).toHaveBeenLastCalledWith(true);
    click(element, "Close");
    expect(api.danger).toHaveBeenCalled();
    expect(api.call.mock.calls[0][1].doc.title).toBe("Submitted");
  });
});

it("adopts saved keys by identity when steps are removed during a save", async () => {
  let finish;
  api.call.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const { element, dirty } = mountBuilder();
  click(element, "Add wait");
  click(element, "Add wait");
  await nextTick();
  click(element, "Save");
  click(element, "Remove first step");
  await nextTick();
  finish(saved(api.call.mock.calls[0][1].doc));
  await settle();
  expect(dirty).toHaveBeenLastCalledWith(true);
  click(element, "Save");
  expect(
    api.call.mock.calls[1][1].doc.actions.map((row) => row.step_key)
  ).toEqual(["wait_2"]);
});

it("preserves step keys edited during a pending save", async () => {
  let finish;
  api.call.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      })
  );
  const { element, dirty } = mountBuilder();
  click(element, "Add wait");
  await nextTick();
  click(element, "Save");
  click(element, "Rename first step");
  await nextTick();
  finish(saved(api.call.mock.calls[0][1].doc));
  await settle();
  expect(dirty).toHaveBeenLastCalledWith(true);
  click(element, "Save");
  expect(api.call.mock.calls[1][1].doc.actions[0].step_key).toBe(
    "renamed_wait"
  );
});
