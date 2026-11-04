// The header's `status` item: docstatus for a submittable, the workflow state when a workflow governs.
import { describe, expect, it, vi } from "vitest";
import { createApp } from "vue";

vi.mock("@/i18n", () => ({ __: (text: string) => text }));

import RecordStatus from "../RecordStatus.vue";
import { statusItems } from "../recordStatus";

const submittable = { is_submittable: 1 };

function shown(meta: any, doc: Record<string, any>) {
  return statusItems(meta, doc).map((item) => item.props);
}

describe("statusItems", () => {
  it("draws Draft, Submitted and Cancelled for a submittable doctype", () => {
    expect(shown(submittable, { docstatus: 0 })).toEqual([{ label: "Draft", theme: "gray" }]);
    expect(shown(submittable, { docstatus: 1 })).toEqual([{ label: "Submitted", theme: "blue" }]);
    expect(shown(submittable, { docstatus: 2 })).toEqual([{ label: "Cancelled", theme: "red" }]);
  });

  it("draws nothing for a doctype that cannot submit", () => {
    expect(statusItems({ is_submittable: 0 }, { docstatus: 0 })).toEqual([]);
    expect(statusItems(null, {})).toEqual([]);
  });

  it("draws the workflow state instead of the docstatus", () => {
    const meta = { ...submittable, workflow_state_field: "workflow_state" };
    expect(shown(meta, { docstatus: 1, workflow_state: "Approved" })).toEqual([
      { label: "Approved", theme: "gray" },
    ]);
  });

  it("colours the workflow state by its Workflow State's style", () => {
    const meta = {
      workflow_state_field: "workflow_state",
      workflow_state_styles: { Approved: "Success", Rejected: "Danger", Waiting: "Warning" },
    };
    expect(shown(meta, { workflow_state: "Approved" })[0]).toMatchObject({ theme: "green" });
    expect(shown(meta, { workflow_state: "Rejected" })[0]).toMatchObject({ theme: "red" });
    expect(shown(meta, { workflow_state: "Waiting" })[0]).toMatchObject({ theme: "orange" });
  });

  it("falls back to the docstatus while the state field is empty", () => {
    const meta = { ...submittable, workflow_state_field: "workflow_state" };
    expect(shown(meta, { docstatus: 0, workflow_state: null })).toEqual([
      { label: "Draft", theme: "gray" },
    ]);
  });

  it("is a left-zone item named status, so a script can replace or hide it", () => {
    const [item] = statusItems(submittable, { docstatus: 0 });
    expect(item).toMatchObject({ name: "status", zone: "left", component: RecordStatus });
  });
});

describe("RecordStatus", () => {
  it("draws a Badge with the label", () => {
    const host = document.createElement("div");
    createApp(RecordStatus, { label: "Submitted", theme: "blue" }).mount(host);
    expect(host.textContent?.trim()).toBe("Submitted");
  });
});
