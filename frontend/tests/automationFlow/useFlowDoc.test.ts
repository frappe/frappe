// The flow document composable alone: undo and redo, the first save, and the errors of a refused one.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const fake = vi.hoisted(() => ({
  getDocument: vi.fn(),
  createDocument: vi.fn(),
  updateDocument: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  getDocument: fake.getDocument,
  createDocument: fake.createDocument,
  updateDocument: fake.updateDocument,
}));
vi.mock("frappe-ui", async (importOriginal) => {
  const original = await importOriginal<any>();
  return { ...original, toast: { ...original.toast, error: fake.toastError } };
});

import { ApiError } from "@framework/ui/api";
import { useFlowDoc } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/useFlowDoc";
import {
  insertAfter,
  newStep,
  removeStep,
} from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowSteps";

const row = (idx: number, extra = {}) => ({
  name: `row-${idx}`,
  idx,
  step_type: "Action",
  action_type: "SetFieldValue",
  step_key: `step_${idx}`,
  params: "{}",
  parent_step: 0,
  branch: "",
  ...extra,
});

const saved = () => ({
  name: "AUTO-00001",
  title: "Notify",
  document_type: "ToDo",
  trigger_type: "Document Created",
  filters: '[["status","=","Open"]]',
  condition: "doc.priority == 'High'",
  modified: "2026-11-11 10:00:00",
  actions: [row(1), row(2)],
});

let now = 1_000_000;
// Edits within 600 ms share one undo step, so each test edit moves the clock past that.
async function edit(change: () => void) {
  now += 1000;
  vi.setSystemTime(now);
  change();
  await nextTick();
  await nextTick();
}

async function openSaved() {
  fake.getDocument.mockResolvedValue({ data: saved() });
  const flow = useFlowDoc("AUTO-00001");
  await flow.load();
  return flow;
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("undo and redo", () => {
  it("steps back and forward across adding, editing and deleting a node", async () => {
    const flow = await openSaved();
    const added = newStep({ action_type: "SetFieldValue" });

    await edit(() => insertAfter(flow.doc.actions, flow.doc.actions[1], added));
    await edit(() => (flow.doc.actions[0].params = '{"field":"status"}'));
    await edit(() => removeStep(flow.doc.actions, flow.doc.actions[1]));
    expect(flow.doc.actions.map((s: any) => s.step_key)).toEqual(["step_1", ""]);

    flow.undo();
    expect(flow.doc.actions.map((s: any) => s.step_key)).toEqual(["step_1", "step_2", ""]);
    flow.undo();
    expect(flow.doc.actions[0].params).toBe("{}");
    flow.undo();
    expect(flow.doc.actions).toHaveLength(2);
    expect(flow.canUndo).toBe(false);
    expect(flow.unsaved).toBe(false);

    flow.redo();
    flow.redo();
    flow.redo();
    expect(flow.doc.actions.map((s: any) => s.step_key)).toEqual(["step_1", ""]);
    expect(flow.doc.actions[0].params).toBe('{"field":"status"}');
    expect(flow.canRedo).toBe(false);
  });

  it("drops the redo steps when a new edit follows an undo", async () => {
    const flow = await openSaved();

    await edit(() => (flow.doc.title = "One"));
    flow.undo();
    expect(flow.canRedo).toBe(true);
    await edit(() => (flow.doc.title = "Two"));

    expect(flow.canRedo).toBe(false);
  });

  it("restores the Filters and Condition a DocType change cleared", async () => {
    const flow = await openSaved();

    await edit(() =>
      Object.assign(flow.doc, { document_type: "Note", filters: "[]", condition: "" })
    );
    expect(flow.doc.condition).toBe("");

    flow.undo();
    expect(flow.doc.document_type).toBe("ToDo");
    expect(flow.doc.filters).toBe('[["status","=","Open"]]');
    expect(flow.doc.condition).toBe("doc.priority == 'High'");
    expect(flow.unsaved).toBe(false);

    flow.redo();
    expect(flow.doc.document_type).toBe("Note");
    expect(flow.doc.condition).toBe("");
  });
});

describe("the first save", () => {
  it("keeps the undo history and undoes into the saved flow, not into a new one", async () => {
    const flow = useFlowDoc(null);
    await flow.load();
    fake.createDocument.mockResolvedValue({
      data: { ...saved(), title: "Second", actions: [] },
    });

    await edit(() => (flow.doc.title = "First"));
    await edit(() => (flow.doc.title = "Second"));
    expect(await flow.save()).toBe(true);
    expect(flow.canUndo).toBe(true);

    flow.undo();
    expect(flow.doc.title).toBe("First");
    expect(flow.doc.name).toBe("AUTO-00001");
    expect(flow.doc.modified).toBe("2026-11-11 10:00:00");
    expect(flow.isNew).toBe(false);
    expect(flow.unsaved).toBe(true);

    await nextTick();
    expect(flow.canRedo).toBe(true);
    flow.redo();
    expect(flow.doc.title).toBe("Second");
    flow.undo();
    await nextTick();

    fake.updateDocument.mockResolvedValue({ data: { ...saved(), title: "First", actions: [] } });
    await flow.save();
    expect(fake.createDocument).toHaveBeenCalledOnce();
    expect(fake.updateDocument).toHaveBeenCalledWith(
      "Automation Flow",
      "AUTO-00001",
      expect.objectContaining({ title: "First" })
    );
  });
});

describe("errors of a refused save", () => {
  const refusal = () =>
    new ApiError(
      {
        type: "ValidationError",
        message: "Zeile 2: Wert fehlt",
        field_errors: [{ fieldname: "params", parentfield: "actions", idx: 2, message: "Wert fehlt" }],
      },
      417
    );

  it("marks the step of the row, in any language", async () => {
    const flow = await openSaved();
    fake.updateDocument.mockRejectedValue(refusal());

    await edit(() => (flow.doc.title = "Renamed"));
    expect(await flow.save()).toBe(false);

    expect(flow.errors).toEqual({ [flow.doc.actions[1]._id]: ["Wert fehlt"] });
    expect(fake.toastError).toHaveBeenCalledWith("Wert fehlt");
  });

  it("clears a node's error when that node is edited, and no other's", async () => {
    const flow = await openSaved();
    fake.updateDocument.mockRejectedValue(refusal());
    await edit(() => (flow.doc.title = "Renamed"));
    await flow.save();
    const failing = flow.doc.actions[1]._id;

    await edit(() => (flow.doc.actions[0].params = '{"field":"status"}'));
    await edit(() => (flow.doc.title = "Renamed again"));
    expect(Object.keys(flow.errors)).toEqual([failing]);

    await edit(() => (flow.doc.actions[1].params = '{"field":"status"}'));
    expect(flow.errors).toEqual({});
  });

  it("clears the trigger's error when a trigger field is edited", async () => {
    const flow = await openSaved();
    fake.updateDocument.mockRejectedValue(
      new ApiError(
        {
          type: "ValidationError",
          message: "x",
          field_errors: [{ fieldname: "trigger_field", message: "Pick a field" }],
        },
        417
      )
    );
    await edit(() => (flow.doc.title = "Renamed"));
    await flow.save();
    expect(flow.errors.trigger).toEqual(["Pick a field"]);

    await edit(() => (flow.doc.trigger_field = "status"));
    expect(flow.errors).toEqual({});
  });
});
