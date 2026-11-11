// The trial run's state machine, mounted in a throwaway component so its unmount hook has a host.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, nextTick, type App } from "vue";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  runMethod: fake.runMethod,
}));

import { ApiError } from "@framework/ui/api";
import { useTrialRun } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/useTrialRun";
import { newStep } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowSteps";

const CALL = "frappe.automation_engine.api.trial_run";

function flow() {
  const check = newStep({ step_type: "If", step_key: "check" });
  const yes = newStep({ step_key: "yes" });
  const no = newStep({ step_key: "no" });
  check.children.If.push(yes);
  check.children.Else.push(no);
  return { name: "AUTO-00001", actions: [check], check, yes, no };
}

const graph = (doc: ReturnType<typeof flow>) => ({
  nodes: [
    { id: "trigger", position: { x: 0, y: 0 }, data: { detail: "on ToDo" } },
    ...[doc.check, doc.yes, doc.no].map((s) => ({
      id: s._id,
      position: { x: 0, y: 0 },
      data: { detail: "Ready" },
    })),
  ],
  edges: [
    { id: "e1", source: doc.check._id, target: doc.yes._id },
    { id: "e2", source: doc.check._id, target: doc.no._id },
  ],
});

const TRACE = {
  status: "Success",
  branches: { "1": "If" },
  steps: [
    { step_key: "check", step_idx: 0, status: "Success", action_type: "", duration_ms: 3 },
    { step_key: "yes", step_idx: 1, status: "Success", message: "Done", duration_ms: 12 },
  ],
};

let app: App;
let doc: ReturnType<typeof flow>;
let trial: ReturnType<typeof useTrialRun>;

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  doc = flow();
  app = createApp(
    defineComponent({
      setup() {
        trial = useTrialRun(() => doc);
        return () => null;
      },
    })
  );
  app.mount(document.createElement("div"));
});

afterEach(() => {
  app.unmount();
  vi.useRealTimers();
});

const nodeOf = (id: string) => trial.decorate(graph(doc).nodes, graph(doc).edges).nodes.find((n) => n.id === id)!;

describe("a trial run", () => {
  it("calls trial_run with POST semantics, the saved flow and the picked record", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    trial.pickDocument("TODO-1");
    const running = trial.run();
    await vi.runAllTimersAsync();
    await running;
    expect(fake.runMethod).toHaveBeenCalledWith(CALL, {
      automation: "AUTO-00001",
      docname: "TODO-1",
      branch_overrides: {},
    });
    expect(fake.runMethod.mock.calls[0][2]).toBeUndefined();
  });

  it("plays the trace one step at a time and then dims the arm it did not take", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    const running = trial.run();
    await vi.advanceTimersByTimeAsync(0);
    expect(trial.playing).toBe(true);
    expect(nodeOf(doc.check._id).data.run?.status).toBe("running");
    await vi.runAllTimersAsync();
    await running;
    expect(trial.playing).toBe(false);
    expect(trial.ranCount).toBe(2);
    expect(trial.stepCount).toBe(3);
    expect(nodeOf(doc.yes._id).data.run).toMatchObject({ status: "Success", durationMs: 12 });
    expect(nodeOf(doc.yes._id).data.detail).toBe("Done");
    expect(nodeOf(doc.no._id).data.dimmed).toBe(true);
    expect(nodeOf(doc.yes._id).data.dimmed).toBe(false);
  });

  it("dashes the edge into the arm it did not take", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    const running = trial.run();
    await vi.runAllTimersAsync();
    await running;
    const { edges } = trial.decorate(graph(doc).nodes, graph(doc).edges);
    expect(edges.find((e) => e.id === "e2")?.style).toMatchObject({ strokeDasharray: "4 4" });
    expect(edges.find((e) => e.id === "e1")?.style).toBeUndefined();
  });

  it("jumps to the end on Skip", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    const running = trial.run();
    await vi.advanceTimersByTimeAsync(0);
    trial.skip();
    expect(trial.playing).toBe(false);
    expect(trial.ranCount).toBe(2);
    await vi.runAllTimersAsync();
    await running;
    expect(trial.ranCount).toBe(2);
  });

  it("offers the arm it skipped, and re-runs forcing it", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    let running = trial.run();
    await vi.runAllTimersAsync();
    await running;
    expect(nodeOf(doc.check._id).data.run?.retryArms).toEqual([{ key: "Else", label: expect.any(String) }]);

    fake.runMethod.mockResolvedValue({
      data: {
        status: "Success",
        branches: { "1": "Else" },
        steps: [{ step_key: "check", step_idx: 0, status: "Success" }],
      },
    });
    running = trial.runBranch({ nodeId: doc.check._id, arm: { key: "Else", label: "False" } });
    await vi.runAllTimersAsync();
    await running;
    expect(fake.runMethod).toHaveBeenLastCalledWith(
      CALL,
      expect.objectContaining({ branch_overrides: { "1": "Else" } })
    );
    expect(nodeOf(doc.check._id).data.run?.forced).toBe(true);
  });

  it("clears the forced arm when a fresh run starts", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    let running = trial.runBranch({ nodeId: doc.check._id, arm: { key: "Else", label: "False" } });
    await vi.runAllTimersAsync();
    await running;
    running = trial.run();
    await vi.runAllTimersAsync();
    await running;
    expect(fake.runMethod).toHaveBeenLastCalledWith(CALL, expect.objectContaining({ branch_overrides: {} }));
  });

  it("lists the failed steps and reads the server message as plain text", async () => {
    fake.runMethod.mockResolvedValueOnce({
      data: {
        status: "Failed",
        branches: {},
        steps: [{ step_key: "check", step_idx: 0, status: "Failed", message: "Boom", traceback: "Trace" }],
      },
    });
    const running = trial.run();
    await vi.runAllTimersAsync();
    await running;
    expect(trial.failures).toHaveLength(1);
    expect(nodeOf(doc.check._id).data.run?.status).toBe("Failed");

    fake.runMethod.mockRejectedValueOnce(
      new ApiError({ type: "ValidationError", message: "<b>Not</b> allowed" }, 417)
    );
    await trial.run();
    expect(trial.error).toBe("Not allowed");
    expect(trial.summary).toBeNull();
  });

  it("forgets the run and the picked record on close", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    trial.pickDocument("TODO-1");
    const running = trial.run();
    await vi.runAllTimersAsync();
    await running;
    trial.close();
    expect(trial.summary).toBeNull();
    expect(trial.docname).toBe("");
    expect(nodeOf(doc.yes._id).data.run).toBeUndefined();
  });
  it("drops a response that lands after the bar was closed", async () => {
    let answer!: (value: { data: typeof TRACE }) => void;
    fake.runMethod.mockReturnValue(new Promise((resolve) => (answer = resolve)));
    const running = trial.run();
    expect(trial.running).toBe(true);
    trial.close();
    expect(trial.running).toBe(false);
    answer({ data: TRACE });
    await vi.runAllTimersAsync();
    await running;
    expect(trial.summary).toBeNull();
    expect(nodeOf(doc.yes._id).data.run).toBeUndefined();
  });

  it("drops a response that lands after another record was picked", async () => {
    let answer!: (value: { data: typeof TRACE }) => void;
    fake.runMethod.mockReturnValue(new Promise((resolve) => (answer = resolve)));
    trial.pickDocument("TODO-1");
    const running = trial.run();
    trial.pickDocument("TODO-2");
    answer({ data: TRACE });
    await vi.runAllTimersAsync();
    await running;
    expect(trial.docname).toBe("TODO-2");
    expect(trial.summary).toBeNull();
  });

  it("keeps the spinner of the latest run when an earlier one settles", async () => {
    const answers: Array<(value: { data: typeof TRACE }) => void> = [];
    fake.runMethod.mockImplementation(() => new Promise((resolve) => answers.push(resolve)));
    const first = trial.run();
    const second = trial.run();
    answers[0]({ data: TRACE });
    await first;
    expect(trial.running).toBe(true);
    expect(trial.summary).toBeNull();
    answers[1]({ data: TRACE });
    await vi.runAllTimersAsync();
    await second;
    expect(trial.running).toBe(false);
    expect(trial.summary).toEqual(TRACE);
  });

  it("starts over when a run is started during playback", async () => {
    fake.runMethod.mockResolvedValue({ data: TRACE });
    const first = trial.run();
    await vi.advanceTimersByTimeAsync(0);
    expect(trial.playing).toBe(true);
    const second = trial.run();
    await vi.runAllTimersAsync();
    await Promise.all([first, second]);
    expect(trial.playing).toBe(false);
    expect(trial.running).toBe(false);
    expect(nodeOf(doc.yes._id).data.run?.status).toBe("Success");
    expect(fake.runMethod).toHaveBeenCalledTimes(2);
  });

  it("shows a failed request and leaves the canvas blank", async () => {
    fake.runMethod.mockRejectedValue(new Error("Network down"));
    await trial.run();
    expect(trial.error).toBe("Network down");
    expect(trial.running).toBe(false);
    expect(trial.summary).toBeNull();
    expect(nodeOf(doc.check._id).data.run).toBeUndefined();
  });

  it("reads a wait for event's branch from the outcome row folded into it", async () => {
    const wait = newStep({ step_type: "WaitForEvent", step_key: "wait" });
    const yes = newStep({ step_key: "yes" });
    const no = newStep({ step_key: "no" });
    wait._outcomeKey = "wait_outcome";
    wait.children.If.push(yes);
    wait.children.Else.push(no);
    doc.actions = [wait];
    fake.runMethod.mockResolvedValue({
      data: {
        status: "Success",
        branches: { "2": "If" },
        steps: [
          { step_key: "wait", step_idx: 0, status: "Success", action_type: "WaitForEvent" },
          { step_key: "wait_outcome", step_idx: 1, status: "Success" },
          { step_key: "yes", step_idx: 2, status: "Success" },
        ],
      },
    });
    const running = trial.run();
    await vi.runAllTimersAsync();
    await running;
    const node = (step: typeof yes) =>
      trial.decorate([{ id: step._id, position: { x: 0, y: 0 }, data: {} }], []).nodes[0];
    expect(node(yes).data.dimmed).toBe(false);
    expect(node(no).data.dimmed).toBe(true);
    expect(node(wait).data.run?.retryArms).toEqual([expect.objectContaining({ key: "Else" })]);
  });
});
