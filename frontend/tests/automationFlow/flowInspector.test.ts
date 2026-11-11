// The inspector mounted on its own: the builder owns the document, so it is read from the emitted patches.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, reactive, type App } from "vue";

vi.mock("@framework/ui/Link", () => ({
  Link: defineComponent({
    props: ["modelValue", "label", "doctype"],
    emits: ["update:modelValue"],
    setup: (props, { emit }) => () =>
      h("input", {
        "data-link": props.doctype,
        value: props.modelValue,
        onChange: (e: Event) => emit("update:modelValue", (e.target as HTMLInputElement).value),
      }),
  }),
}));

import ParamEditor from "../../../frappe/automation/doctype/automation_flow/frontend/inspector/ParamEditor.vue";
import FlowInspector from "../../../frappe/automation/doctype/automation_flow/frontend/inspector/FlowInspector.vue";

let app: App;
let host: HTMLElement;

async function mount(props: Record<string, unknown>) {
  const events: Record<string, any[]> = { update: [], remove: [] };
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(FlowInspector, {
        ...props,
        onUpdate: (values: object) => events.update.push(values),
        onRemove: () => events.remove.push(true),
      }),
  });
  app.mount(host);
  await settle();
  return events;
}

async function settle() {
  for (let i = 0; i < 4; i++) await nextTick();
  await new Promise((resolve) => setTimeout(resolve));
}

const button = (label: string) =>
  [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === label) as
    | HTMLElement
    | undefined;

afterEach(() => {
  app.unmount();
  host.remove();
});

describe("the inspector's trigger view", () => {
  it("patches the document type from the DocType control", async () => {
    const events = await mount({ doc: reactive({ document_type: "", trigger_type: "" }) });
    const link = host.querySelector("[data-link=DocType]") as HTMLInputElement;

    link.value = "ToDo";
    link.dispatchEvent(new Event("change"));

    expect(events.update).toEqual([
      {
        document_type: "ToDo",
        trigger_field: null,
        from_value: null,
        to_value: null,
        date_field: null,
        custom_event: null,
      },
    ]);
  });

  it("lists the events and patches the trigger the owner picks", async () => {
    const events = await mount({ doc: reactive({ document_type: "ToDo", trigger_type: "" }) });

    button("Choose an event")!.click();
    await settle();
    [...host.querySelectorAll("button")]
      .find((b) => b.textContent?.includes("Record is created"))!
      .click();
    await settle();

    expect(events.update[0]).toMatchObject({ trigger_type: "Doc Created" });
    expect(host.textContent).toContain("Trigger");
  });

  it("offers Delete trigger only once a trigger is set", async () => {
    const empty = await mount({ doc: reactive({ document_type: "ToDo", trigger_type: "" }) });
    expect(button("Delete trigger")).toBeUndefined();
    app.unmount();
    host.remove();

    const set = await mount({ doc: reactive({ document_type: "ToDo", trigger_type: "Doc Created" }) });
    button("Delete trigger")!.click();

    expect(set.remove).toEqual([true]);
    expect(empty.remove).toEqual([]);
  });
});

describe("the inspector's step view", () => {
  const waitStep = () =>
    reactive({
      _id: "s1",
      step_type: "Wait",
      params: JSON.stringify({ value: 5, unit: "Minutes" }),
      children: {},
    });

  it("writes an edited param back to the step's params JSON", async () => {
    const step = waitStep();
    await mount({ doc: reactive({ document_type: "ToDo", actions: [step] }), selectedStep: step });

    const amount = host.querySelector("input[type=number]") as HTMLInputElement;
    amount.value = "9";
    amount.dispatchEvent(new Event("input"));
    await settle();

    expect(JSON.parse(step.params).value).toBe(9);
  });

  it("clears the wait amount when the box is emptied instead of saving zero", async () => {
    const step = waitStep();
    await mount({ doc: reactive({ document_type: "ToDo", actions: [step] }), selectedStep: step });

    const amount = host.querySelector("input[type=number]") as HTMLInputElement;
    amount.value = "";
    amount.dispatchEvent(new Event("input"));
    await settle();

    expect(JSON.parse(step.params).value).toBeNull();
  });

  it("asks to delete the step, not the trigger", async () => {
    const step = waitStep();
    const events = await mount({
      doc: reactive({ document_type: "ToDo", actions: [step] }),
      selectedStep: step,
    });

    button("Delete step")!.click();

    expect(button("Delete trigger")).toBeUndefined();
    expect(events.remove).toEqual([true]);
  });

  it("renders a step whose stored params are JSON null", async () => {
    const step = reactive({ ...waitStep(), params: "null" });

    await mount({ doc: reactive({ document_type: "ToDo", actions: [step] }), selectedStep: step });

    expect(host.querySelector("input[type=number]")).not.toBeNull();
  });
});

describe("the Advanced Field Values box", () => {
  async function mountAdvanced(action: object) {
    host = document.createElement("div");
    document.body.appendChild(host);
    app = createApp({ render: () => h(ParamEditor, { action, advanced: true }) });
    app.mount(host);
    await settle();
    return host.querySelector("textarea") as HTMLTextAreaElement;
  }

  async function type(box: HTMLTextAreaElement, text: string) {
    box.value = text;
    box.dispatchEvent(new Event("input"));
    await settle();
  }

  it("keeps half-typed JSON in the box and saves it once it parses", async () => {
    const action = reactive({ action_type: "SetFieldValue", params: "{}" });
    const box = await mountAdvanced(action);

    await type(box, '{"status": "Ju');
    expect(JSON.parse(action.params).values).toBeUndefined();
    expect(box.value).toBe('{"status": "Ju');

    await type(box, '{"status": "Junk"}');
    expect(JSON.parse(action.params).values).toEqual({ status: "Junk" });
  });
});
