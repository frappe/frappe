import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { seedFavourites } from "@/list/favouriteStars";
import type { BulkScope } from "@/list/useBulkScope";
import { useBulkFavourite } from "../bulkFavourite";

const bulkCollaborate = vi.fn();
const runBulk = vi.fn();
vi.mock("@framework/ui/api", () => ({
	bulkCollaborate: (...args: unknown[]) => bulkCollaborate(...args),
	addFavourite: vi.fn(),
	removeFavourite: vi.fn(),
}));
vi.mock("@framework/ui/cache", () => ({ readCachedDocument: () => undefined }));
vi.mock("@/shell/bulkOutcome", () => ({ runBulk: (...args: unknown[]) => runBulk(...args) }));

const USER = "jane@example.com";

function setup(selected: string[], all = false) {
	const selection = ref(selected);
	const scope = {
		all: ref(all),
		selected: () => (all ? { filters: [["status", "=", "Open"]] } : { names: selection.value }),
	} as unknown as BulkScope;
	const reload = vi.fn();
	const favourite = useBulkFavourite({ doctype: "ToDo", scope, selection, user: USER, reload });
	const find = (name: string) => favourite.items().find((item) => item.name === name)!;
	const shown = (name: string) => find(name).when!({} as never);
	return { favourite, find, shown, selection, reload };
}

beforeEach(() => {
	bulkCollaborate.mockReset();
	runBulk.mockReset();
	seedFavourites("ToDo", { favourites: ["A"] }, ["A", "B", "C"]);
});

describe("useBulkFavourite", () => {
	it("offers Favourite while a selected row is not starred, Unfavourite when every one is", () => {
		const some = setup(["A", "B"]);
		expect([some.shown("favourite_records"), some.shown("unfavourite_records")]).toEqual([true, false]);

		const every = setup(["A"]);
		expect([every.shown("favourite_records"), every.shown("unfavourite_records")]).toEqual([false, true]);
	});

	it("keeps the button on Favourite under Select all, and adds Unfavourite to More", () => {
		const all = setup([], true);
		expect([all.shown("favourite_records"), all.shown("unfavourite_records")]).toEqual([true, false]);
		expect(all.shown("unfavourite_matching")).toBe(true);
		expect(all.find("unfavourite_matching").button).toBeUndefined();
		expect(setup(["A"]).shown("unfavourite_matching")).toBe(false);
	});

	it("sends POST to favourite and DELETE to unfavourite, on the names or the filters", async () => {
		const names = setup(["A", "B"]);
		await names.find("favourite_records").run!({} as never);
		const { send } = runBulk.mock.calls[0][0];
		await send();
		expect(bulkCollaborate).toHaveBeenLastCalledWith("ToDo", "favourites", "POST", { names: ["A", "B"] });
		await send(["B"]);
		expect(bulkCollaborate).toHaveBeenLastCalledWith("ToDo", "favourites", "POST", { names: ["B"] });

		const all = setup([], true);
		await all.find("unfavourite_matching").run!({} as never);
		await runBulk.mock.calls[1][0].send();
		expect(bulkCollaborate).toHaveBeenLastCalledWith("ToDo", "favourites", "DELETE", {
			filters: [["status", "=", "Open"]],
		});
	});

	it("reloads the list when a run ends and recognises its own runs", async () => {
		const { find, favourite, reload } = setup(["A"]);
		await find("unfavourite_records").run!({} as never);
		runBulk.mock.calls[0][0].finished();
		expect(reload).toHaveBeenCalledOnce();
		expect(favourite.takesScope(find("unfavourite_records").run)).toBe(true);
		expect(favourite.takesScope(() => {})).toBe(false);
	});
});
