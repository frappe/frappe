// A list row's actions from `page.rowActions`: each is an act `row_<name>`, drawn in a row's menu
// while the act passes its right and the item's own `when` holds, and run with the page and the row.
import { afterEach, describe, expect, it, vi } from "vitest";
import { acts } from "@/acts/dispatcher";
import type { ListPageApi, ListRow, ListRowAction } from "@/listPage/types";
import { rowActionEntries, rowActionFields, rowMenuOptions } from "../rowActions";
import type { ListActs } from "../listActs";

vi.mock("frappe-ui", () => ({ toast: { error: vi.fn() } }));

const releases: (() => void)[] = [];

afterEach(() => releases.splice(0).forEach((release) => release()));

const page = { doctype: "Lead", selection: ["LEAD-2"] } as unknown as ListPageApi;
const lead: ListRow = { name: "LEAD-1", mobile_no: "+91 98" };

/** The list surface the page registers, drawn from the same entries. */
function listSurface(actions: ListRowAction[], passes: (right?: string) => boolean = () => true): ListActs {
	releases.push(
		acts.register({
			surfaces: { list: () => rowActionEntries(actions) },
			context: () => page,
			passes: (right) => passes(right as string | undefined),
			settled: () => undefined,
			hold: async (work) => work(),
			failed: (error) => {
				throw error;
			},
		})
	);
	return {
		context: () => page,
		drawn: (name) => acts.find(`list.${name}`),
		perform: (act, value) => void acts.perform(act.name, value),
	};
}

function callAction(ran: unknown[][], extra: Partial<ListRowAction> = {}): ListRowAction {
	return {
		name: "call",
		label: "Call",
		icon: "lucide-phone",
		fields: ["mobile_no"],
		run: (...args) => void ran.push(args),
		...extra,
	};
}

describe("row actions", () => {
	it("draws an item named for the action, with its label and icon, and runs it with the page and the row", async () => {
		const ran: unknown[][] = [];
		const listActs = listSurface([callAction(ran)]);

		const [option] = rowMenuOptions(lead, [callAction(ran)], listActs);
		expect(acts.find("list.row_call")).toMatchObject({ label: "Call", icon: "lucide-phone" });
		expect(option).toMatchObject({ label: "Call", icon: "lucide-phone" });
		option.onClick();
		await Promise.resolve();
		expect(ran).toEqual([[page, lead]]);
	});

	it("draws nothing when the action's right fails", () => {
		const action = callAction([], { right: "write" });
		const listActs = listSurface([action], (right) => right !== "write");
		expect(rowMenuOptions(lead, [action], listActs)).toEqual([]);
	});

	it("skips a row whose when is false, or throws, and hands when the page and the row", () => {
		const when = vi.fn((_page: ListPageApi, row: ListRow) => {
			if (row.name === "LEAD-3") throw new Error("bad row");
			return row.name !== "LEAD-2";
		});
		const action = callAction([], { when });
		const listActs = listSurface([action]);

		expect(rowMenuOptions(lead, [action], listActs)).toHaveLength(1);
		expect(rowMenuOptions({ name: "LEAD-2" }, [action], listActs)).toEqual([]);
		expect(rowMenuOptions({ name: "LEAD-3" }, [action], listActs)).toEqual([]);
		expect(when).toHaveBeenCalledWith(page, lead);
	});

	it("names the row fields the actions read, for the list query", () => {
		expect(rowActionFields([callAction([]), { name: "open", run: () => {} }])).toEqual(["mobile_no"]);
	});
});
