import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type App } from "vue";
import EditDialog from "../EditDialog.vue";

// Reka's select draws no <select> in jsdom: a native one stands in so a test can pick an option.
vi.mock("frappe-ui", async (importOriginal) => {
	const { defineComponent, h } = await import("vue");
	const Select = defineComponent({
		props: { modelValue: { default: null }, options: { default: () => [] } },
		emits: ["update:modelValue"],
		setup: (props, { emit }) =>
			() =>
				h(
					"select",
					{ value: props.modelValue ?? "", onChange: (event: Event) => emit("update:modelValue", (event.target as HTMLSelectElement).value) },
					[
						h("option", { value: "" }, ""),
						...(props.options as (string | { label: string; value: string })[]).map((one) =>
							typeof one === "string" ? h("option", { value: one }, one) : h("option", { value: one.value }, one.label)
						),
					]
				),
	});
	return { ...(await importOriginal<typeof import("frappe-ui")>()), Select };
});
vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<object>()),
	getMeta: vi.fn(async () => ({
		data: {
			fields: [
				{ fieldname: "description", label: "Description", fieldtype: "Data" },
				{ fieldname: "priority", label: "Priority", fieldtype: "Select", options: "Low\nHigh" },
				{ fieldname: "locked", label: "Locked", fieldtype: "Data", read_only: 1 },
				{ fieldname: "done", label: "Done", fieldtype: "Check" },
				{
					fieldname: "note",
					label: "Note",
					fieldtype: "Data",
					description: "Shown to the assignee",
					depends_on: "eval:doc.status == 'Open'",
				},
			],
		},
		children: {},
	})),
}));

let mounted: App | null = null;

async function settle() {
	for (let turn = 0; turn < 6; turn++) await nextTick();
	await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

async function open(run: (update: unknown) => Promise<void>, scope = {}) {
	const host = document.createElement("div");
	document.body.append(host);
	const shown = ref(true);
	mounted = createApp({
		render: () =>
			h(EditDialog, {
				modelValue: shown.value,
				"onUpdate:modelValue": (value: boolean) => (shown.value = value),
				doctype: "ToDo",
				count: 2,
				...scope,
				run,
			}),
	});
	mounted.mount(host);
	await settle();
	return shown;
}

const text = () => document.body.textContent ?? "";
const button = (label: string) =>
	Array.from(document.body.querySelectorAll("button")).find((one) => one.textContent?.trim() === label);

async function pick(label: string) {
	const select = document.body.querySelector("select")!;
	const option = Array.from(select.options).find((one) => one.textContent?.trim() === label)!;
	select.value = option.value;
	select.dispatchEvent(new Event("change", { bubbles: true }));
	await settle();
}

afterEach(() => {
	mounted?.unmount();
	mounted = null;
	document.body.innerHTML = "";
	vi.clearAllMocks();
});

describe("EditDialog", () => {
	it("names the scope and offers only the fields a bulk edit may set", async () => {
		await open(async () => {});
		expect(text()).toContain("Edit 2 selected records");
		const labels = Array.from(document.body.querySelector("select")!.options).map((one) => one.textContent?.trim());
		expect(labels).toContain("Description");
		expect(labels).toContain("Priority");
		expect(labels).not.toContain("Locked");
		expect(button("Update")!.disabled).toBe(true);
	});

	it("draws the value as one bare control: no label, description or condition", async () => {
		await open(async () => {});
		await pick("Note");
		const row = document.body.querySelector("[role='group'][aria-label='Note']")!;
		expect(row.querySelector("input[placeholder='Note']")).not.toBeNull();
		expect(row.querySelector("label")).toBeNull();
		expect(text()).not.toContain("Value");
		expect(text()).not.toContain("Shown to the assignee");
	});

	it("draws a Check value as a bare checkbox in a group named for the field", async () => {
		await open(async () => {});
		await pick("Done");
		const row = document.body.querySelector("[role='group'][aria-label='Done']")!;
		expect(row.querySelector("input[type='checkbox']")).not.toBeNull();
		expect(row.querySelector("label")).toBeNull();
	});

	it("names every matching record when the run takes the filters", async () => {
		await open(async () => {}, { all: true, count: 10000, approx: true });
		expect(text()).toContain("Edit all 10,000+ matching records");
	});

	it("sends one set of values for the fields picked and closes", async () => {
		const run = vi.fn(async () => {});
		const shown = await open(run);
		await pick("Priority");
		const priority = document.body.querySelectorAll("select")[1] as HTMLSelectElement;
		priority.value = "High";
		priority.dispatchEvent(new Event("change", { bubbles: true }));
		await settle();
		button("Update")!.click();
		await settle();
		expect(run).toHaveBeenCalledWith({ values: { priority: "High" } });
		expect(shown.value).toBe(false);
	});

	it("notes that a picked field with no value is set to empty, and drops the note once it has one", async () => {
		const note = "You have not entered a value. The field will be set to empty.";
		await open(async () => {});
		expect(text()).not.toContain(note);
		await pick("Priority");
		expect(text()).toContain(note);
		const priority = document.body.querySelectorAll("select")[1] as HTMLSelectElement;
		priority.value = "High";
		priority.dispatchEvent(new Event("change", { bubbles: true }));
		await settle();
		expect(text()).not.toContain(note);
	});

	it("sends an unticked Check as 0 with no empty note, as v1 does", async () => {
		const run = vi.fn(async () => {});
		await open(run);
		await pick("Done");
		expect(text()).not.toContain("You have not entered a value");
		button("Update")!.click();
		await settle();
		expect(run).toHaveBeenCalledWith({ values: { done: 0 } });
	});

	it("shows why the whole run was refused", async () => {
		const shown = await open(async () => Promise.reject(new Error("Edit is off for this workflow")));
		await pick("Description");
		button("Update")!.click();
		await settle();
		expect(text()).toContain("Edit is off for this workflow");
		expect(shown.value).toBe(true);
	});
});
