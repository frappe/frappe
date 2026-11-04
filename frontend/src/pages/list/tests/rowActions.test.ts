// A list row's app actions: one `list` surface item per action, drawn while the target act is
// available and the action's own `when` holds, and run through the dispatcher with `value(row)`.
import { afterEach, describe, expect, it, vi } from "vitest";
import { acts, type ActEntry } from "@/acts/dispatcher";
import type { ListContext, RowAction } from "@/contributions/types";
import type { View } from "@/list/view";
import { rowActionEntries, rowMenuOptions } from "../rowActions";
import type { ListActs } from "../listActs";

vi.mock("frappe-ui", () => ({ toast: { error: vi.fn() } }));

const releases: (() => void)[] = [];

afterEach(() => releases.splice(0).forEach((release) => release()));

function register(
	surface: string,
	entries: () => ActEntry[],
	passes = () => true,
	context: () => unknown = () => undefined
) {
	releases.push(
		acts.register({
			surfaces: { [surface]: entries },
			context,
			passes,
			settled: () => undefined,
			hold: async (work) => work(),
			failed: (error) => {
				throw error;
			},
		})
	);
}

function callAct(ran: unknown[], right?: string): ActEntry {
	return {
		item: { name: "crm.call", label: "Call", icon: "lucide-phone", right, run: (_c, value) => ran.push(value) },
		hidden: false,
	};
}

const reload = vi.fn();
const view = { doctype: "Lead", key: "list", type: "List" } as View;
const listContext: ListContext<View> = { doctype: "Lead", view, selection: ["LEAD-2"], reload };

/** The list surface the page registers, drawn from the same entries. */
function listSurface(actions: RowAction[]): ListActs {
	register("list", () => rowActionEntries(actions), () => true, () => listContext);
	return {
		context: () => listContext,
		drawn: (name) => acts.find(`list.${name}`),
		perform: (act, value) => void acts.perform(act.name, value),
	};
}

const call: RowAction = {
	act: "shell.crm.call",
	fields: ["mobile_no"],
	value: (row) => row.mobile_no,
};

describe("row actions", () => {
	it("draws an item named for the act, with the act's label and icon, and runs it with value(row)", async () => {
		const ran: unknown[] = [];
		register("shell", () => [callAct(ran)]);
		const listActs = listSurface([call]);
		const row = { name: "LEAD-1", mobile_no: "555" };

		const [option] = rowMenuOptions(row, [call], listActs);
		expect(option).toMatchObject({ label: "Call", icon: "lucide-phone" });
		option.onClick();
		await vi.waitFor(() => expect(ran).toEqual(["555"]));
	});

	it("takes the action's own label and icon over the act's", () => {
		register("shell", () => [callAct([])]);
		const action = { ...call, label: "Ring", icon: "lucide-bell" };
		const [option] = rowMenuOptions({ name: "L" }, [action], listSurface([action]));
		expect(option).toMatchObject({ label: "Ring", icon: "lucide-bell" });
	});

	it("draws nothing while the act is missing, hidden or its right fails", () => {
		const listActs = listSurface([call]);
		expect(rowMenuOptions({ name: "L" }, [call], listActs)).toEqual([]);

		register("shell", () => [{ ...callAct([]), hidden: true }]);
		expect(rowMenuOptions({ name: "L" }, [call], listActs)).toEqual([]);
	});

	it("draws nothing when the act's right fails", () => {
		register("shell", () => [callAct([], "write")], () => false);
		expect(rowMenuOptions({ name: "L" }, [call], listSurface([call]))).toEqual([]);
	});

	it("skips a row whose when is false", () => {
		register("shell", () => [callAct([])]);
		const action = { ...call, when: (row: Record<string, unknown>) => Boolean(row.mobile_no) };
		const listActs = listSurface([action]);

		expect(rowMenuOptions({ name: "A", mobile_no: "1" }, [action], listActs)).toHaveLength(1);
		expect(rowMenuOptions({ name: "B" }, [action], listActs)).toEqual([]);
	});

	it("hides the action on a row whose when throws", () => {
		register("shell", () => [callAct([])]);
		const action = {
			...call,
			when: () => {
				throw new Error("no field");
			},
		};
		expect(rowMenuOptions({ name: "L" }, [action], listSurface([action]))).toEqual([]);
	});

	it("hands value and when the list's context with the row", async () => {
		const ran: unknown[] = [];
		register("shell", () => [callAct(ran)]);
		const seen: ListContext[] = [];
		const action: RowAction = {
			...call,
			when: (_row, list) => (seen.push(list), true),
			value: (_row, list) => list,
		};
		const row = { name: "LEAD-1" };

		const [option] = rowMenuOptions(row, [action], listSurface([action]));
		option.onClick();
		await vi.waitFor(() => expect(ran).toHaveLength(1));

		const expected = { doctype: "Lead", view, selection: ["LEAD-2"], reload, row };
		expect(seen[0]).toEqual(expected);
		expect(ran[0]).toEqual(expected);
		(ran[0] as ListContext).reload();
		expect(reload).toHaveBeenCalledOnce();
	});

	it("keeps the actions off the palette", () => {
		register("shell", () => [callAct([])]);
		const [entry] = rowActionEntries([call]);
		expect(entry.item.palette).toBe(false);
	});
});
