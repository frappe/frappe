// The smaller helpers around the canvas: edges, validation, triggers and the icons capabilities supply.
import { beforeAll, describe, expect, it, vi } from "vitest";
import { workflowEdges } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowEdges";
import {
  firstBlockingRow,
  stepIssue,
  triggerIssue,
} from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowValidation";
import { loadCapabilities } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowCapabilities";
import {
  docTypeChange,
  eventTriggers,
  triggerDefinition,
  triggerFromPick,
  triggerFromValue,
  triggerValue,
} from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowTriggers";
import { actionIcon } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowIcons";
import { newStep } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowSteps";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  runMethod: fake.runMethod,
}));

beforeAll(async () => {
  fake.runMethod.mockResolvedValue({
    data: {
      actions: [
        {
          action_type: "SendNotification",
          icon: "lucide-mail",
          params_schema: [],
        },
        { action_type: "RunScript", icon: null, params_schema: [] },
      ],
      trigger_events: [
        {
          value: "payment_failed",
          label: "Payment failed",
          icon: "lucide-ban",
        },
      ],
    },
  });
  await loadCapabilities("ToDo");
});

describe("workflow edges", () => {
  it("chains the trigger through the steps in order", () => {
    const first = newStep();
    const second = newStep();

    expect(
      workflowEdges([first, second]).map((e: any) => [e.source, e.target])
    ).toEqual([
      ["trigger", first._id],
      [first._id, second._id],
    ]);
  });

  it("labels the arms of an If step and joins both to what follows", () => {
    const branch = newStep({ step_type: "If" });
    const inIf = newStep();
    const inElse = newStep();
    const after = newStep();
    branch.children.If.push(inIf);
    branch.children.Else.push(inElse);

    const edges = workflowEdges([branch, after]);

    expect(
      edges
        .filter((e: any) => e.source === branch._id)
        .map((e: any) => e.target)
    ).toEqual([inIf._id, inElse._id]);
    expect(edges.filter((e: any) => e.target === after._id)).toHaveLength(2);
  });
});

describe("workflow validation", () => {
  it("asks a trigger for what it still needs, and nothing once it has it", () => {
    expect(triggerIssue({ trigger_type: "Scheduled" })).not.toBe("");
    expect(
      triggerIssue({ trigger_type: "Scheduled", cron_expression: "* * * * *" })
    ).toBe("");
    expect(triggerIssue({ trigger_type: "" })).toBe("");
  });

  it("names what an unfinished step is missing", () => {
    expect(stepIssue(newStep({ step_type: "If" }))).not.toBe("");
    expect(stepIssue(newStep({ step_type: "If", step_condition: "x" }))).toBe(
      ""
    );
    expect(stepIssue(newStep())).not.toBe("");
  });

  it("finds the first row that blocks a run", () => {
    const ready = newStep({ step_type: "If", step_condition: "x" });
    const blocked = newStep({ step_type: "Wait" });

    expect(firstBlockingRow([ready, blocked])?.row.step_type).toBe("Wait");
    expect(firstBlockingRow([ready])).toBeUndefined();
  });
});

describe("workflow triggers", () => {
  it("splits a picker value into the stored trigger and event, and back", () => {
    const picked = triggerFromValue("Custom Event:payment_failed");

    expect(picked).toEqual({
      trigger_type: "Custom Event",
      custom_event: "payment_failed",
    });
    expect(triggerValue(picked)).toBe("Custom Event:payment_failed");
  });

  it("drops the details of the trigger it replaces and those of a changed DocType", () => {
    expect(triggerFromPick("Doc Created")).toMatchObject({
      trigger_type: "Doc Created",
      trigger_field: null,
      cron_expression: null,
      date_field: null,
    });
    expect(triggerFromPick("Scheduled")).not.toHaveProperty("cron_expression");
    expect(docTypeChange("Task")).toMatchObject({ document_type: "Task", trigger_field: null });
  });

  it("offers the domain events of the DocType and defines the chosen one", () => {
    const doc = {
      document_type: "ToDo",
      trigger_type: "Custom Event",
      custom_event: "payment_failed",
    };

    expect(eventTriggers("ToDo").map((t: any) => t.label)).toEqual([
      "Payment failed",
    ]);
    expect(triggerDefinition(doc)?.label).toBe("Payment failed");
  });
});

describe("capability icons", () => {
  it("uses the icon the server sent, and one fallback when it sent none", () => {
    expect(actionIcon("SendNotification").icon).toBe("lucide-mail");
    expect(actionIcon("RunScript").icon).toBe("lucide-zap");
    expect(actionIcon("Unregistered").icon).toBe("lucide-zap");
  });

  it("gives an event trigger its own icon", () => {
    expect(eventTriggers("ToDo")[0].icon).toBe("lucide-ban");
  });
});
