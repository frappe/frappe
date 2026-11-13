import { afterEach, describe, expect, it } from "vitest";
import { GridColumns } from "../gridColumns";
import { mountEditor, taskNote } from "./editorFixture";

const line = () =>
	taskNote({
		doctype: "Task Note Line",
		layouts: {},
		definition: {
			name: "Task Note Line",
			istable: 1,
			fields: [
				{ fieldname: "item", label: "Item", fieldtype: "Link", options: "Item", in_list_view: 1, columns: 3 },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", in_list_view: 1 },
				{ fieldname: "notes", label: "Notes", fieldtype: "Small Text" },
				{ fieldname: "rate", label: "Rate", fieldtype: "Currency", in_list_view: 1, columns: 10 },
				{ fieldname: "break", fieldtype: "Section Break" },
			],
		},
	});

let stop: () => void;
afterEach(() => stop());

function mount() {
	const mounted = mountEditor(line());
	stop = mounted.stop;
	return { mounted, grid: new GridColumns(mounted.canvas) };
}

const names = (fields: { fieldname: string }[]) => fields.map((field) => field.fieldname);
const field = (mounted: ReturnType<typeof mountEditor>, fieldname: string) => mounted.canvas.field(fieldname)!;

describe("the Grid columns group", () => {
	it("lists the in_list_view fields in field order, and the others a column can show", () => {
		const { grid } = mount();
		expect(names(grid.columns.value)).toEqual(["item", "qty", "rate"]);
		expect(names(grid.candidates.value)).toEqual(["notes"]);
		expect(grid.fit.value).toEqual({ room: 608, used: 140 + 100 + 500, over: true });
	});

	it("moves a column by moving its field, so the column order is the field order", async () => {
		const { mounted, grid } = mount();
		grid.move("rate", 0);
		await Promise.resolve();
		expect(names(mounted.canvas.working.value.fields)).toEqual(["rate", "item", "qty", "notes", "break"]);
		grid.move("rate", 2);
		await Promise.resolve();
		expect(names(grid.columns.value)).toEqual(["item", "qty", "rate"]);
		expect(names(mounted.canvas.working.value.fields)).toEqual(["item", "qty", "rate", "notes", "break"]);
	});

	it("steps columns between Auto and 10", async () => {
		const { mounted, grid } = mount();
		grid.step(field(mounted, "qty"), 1);
		await Promise.resolve();
		expect(field(mounted, "qty").columns).toBe(1);
		grid.step(field(mounted, "qty"), -1);
		await Promise.resolve();
		expect(field(mounted, "qty").columns).toBe(0);
		grid.step(field(mounted, "qty"), -1);
		grid.step(field(mounted, "rate"), 1);
		await Promise.resolve();
		expect([field(mounted, "qty").columns, field(mounted, "rate").columns]).toEqual([0, 10]);
		expect(mounted.edits.staged.value.at(-1)).toMatchObject({ fieldname: "rate", property: "columns", value: 10 });
	});

	it("takes a column off the grid with ×, and puts a field on it with Add column", async () => {
		const { mounted, grid } = mount();
		grid.remove("qty");
		grid.add("notes");
		await Promise.resolve();
		expect(names(grid.columns.value)).toEqual(["item", "notes", "rate"]);
		expect([field(mounted, "qty").in_list_view, field(mounted, "notes").in_list_view]).toEqual([0, 1]);
	});
});
