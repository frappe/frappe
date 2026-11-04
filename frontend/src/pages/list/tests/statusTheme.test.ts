// A status or workflow state value takes its Badge theme from meta alone, in desk v1's indicator order.
import { describe, expect, it } from "vitest";
import { listStatusTheme, workflowTheme } from "@/statusTheme";

const workflowMeta = {
	workflow_state_field: "workflow_state",
	workflow_state_styles: { Approved: "Success", Waiting: "Warning", Refused: "Danger", Fresh: "Primary" },
};

describe("workflowTheme", () => {
	it("maps the Workflow State's style to a Badge theme", () => {
		expect(workflowTheme(workflowMeta, "Approved")).toBe("green");
		expect(workflowTheme(workflowMeta, "Waiting")).toBe("orange");
		expect(workflowTheme(workflowMeta, "Refused")).toBe("red");
		expect(workflowTheme(workflowMeta, "Fresh")).toBe("blue");
		expect(workflowTheme({ workflow_state_styles: { S: "Info" } }, "S")).toBe("blue");
	});

	it("is gray for a state with no style, and for no meta", () => {
		expect(workflowTheme(workflowMeta, "Other")).toBe("gray");
		expect(workflowTheme(null, "Approved")).toBe("gray");
	});
});

const fields = [{ fieldname: "status", fieldtype: "Select" }];

describe("listStatusTheme", () => {
	it("colours the workflow state field from the style, not from the words", () => {
		expect(listStatusTheme(workflowMeta, "workflow_state", "Approved")).toBe("green");
		expect(listStatusTheme(workflowMeta, "workflow_state", "Open")).toBe("gray");
	});

	it("takes the status field's colour from a Document States row first", () => {
		const meta = { fields, states: [{ title: "Open", color: "Green" }, { title: "Stuck", color: "Pink" }] };
		expect(listStatusTheme(meta, "status", "Open")).toBe("green");
		expect(listStatusTheme(meta, "status", "Stuck")).toBe("red");
	});

	it("falls back to desk v1's word map", () => {
		const theme = (value: string) => listStatusTheme({ fields }, "status", value);
		expect(theme("Pending")).toBe("orange");
		expect(theme("Not Approved")).toBe("orange");
		expect(theme("Open")).toBe("red");
		expect(theme("Completed")).toBe("green");
		expect(theme("Submitted")).toBe("blue");
		expect(theme("Draft")).toBe("gray");
	});

	it("is null for any other column, an empty value, and a Link status", () => {
		expect(listStatusTheme({}, "priority", "High")).toBeNull();
		expect(listStatusTheme({ fields }, "status", "")).toBeNull();
		expect(listStatusTheme({ fields }, "status", null)).toBeNull();
		const link = { fields: [{ fieldname: "status", fieldtype: "Link" }] };
		expect(listStatusTheme(link, "status", "Open")).toBeNull();
		expect(listStatusTheme({}, "status", "Open")).toBeNull();
	});
});
