import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ addFavourite: vi.fn(), removeFavourite: vi.fn() }));
vi.mock("@framework/ui/api", () => api);
import { fetchFields } from "../defaults";
import { isStarred, seedFavourites, toggleStar } from "../favouriteStars";
import { commentCountOf, partsFor, personOf, seedRowParts } from "../rowParts";
import { columnsFrom, sortFrom } from "../storedSettings";

const readable = () => true;
const stored = ["_assign", "_favourite", "docstatus", "title"].map((fieldname) => ({ fieldname }));

describe("collaboration columns", () => {
	it("keeps Document Status only on a submittable doctype", () => {
		const names = (meta = {}) => columnsFrom(stored, [], readable, meta).map((c) => c.fieldname);
		expect(names()).toEqual(["_assign", "_favourite"]);
		expect(names({ is_submittable: 1 })).toEqual(["_assign", "_favourite", "docstatus"]);
	});

	it("marks every new column but Document Status as not sortable", () => {
		const columns = columnsFrom(stored, [], readable, { is_submittable: 1 });
		expect(columns.map((c) => c.sortable)).toEqual([false, false, undefined]);
	});

	it("sorts by Document Status only on a submittable doctype", () => {
		const sort = [{ fieldname: "docstatus", direction: "asc" }];
		expect(sortFrom(sort, [], readable)).toEqual([]);
		expect(sortFrom(sort, [], readable, { is_submittable: 1 })).toEqual(sort);
		expect(sortFrom([{ fieldname: "_assign", direction: "asc" }], [], readable)).toEqual([]);
	});

	it("asks the server for parts, not for the Favourite or Comments fields", () => {
		const columns = ["_favourite", "_comments", "_assign", "docstatus"].map((fieldname) => ({
			fieldname,
			label: fieldname,
		}));
		expect(fetchFields(columns)).toEqual(["name", "_assign", "docstatus"]);
		expect(partsFor(columns.map((c) => c.fieldname))).toEqual([
			"favourites",
			"users",
			"comment_counts",
		]);
		expect(partsFor(["title"])).toEqual([]);
	});

	it("seeds stars for every row of the page, and people and comment counts", () => {
		seedFavourites("ToDo", { favourites: ["a"] }, ["a", "b"]);
		expect(isStarred("ToDo", "a", "me")).toBe(true);
		expect(isStarred("ToDo", "b", "me")).toBe(false);
		seedRowParts("ToDo", { users: { u1: { full_name: "Ada" } }, comment_counts: { a: 3 } }, ["a", "b"]);
		expect(personOf("u1").name).toBe("Ada");
		expect(personOf("u2").name).toBe("u2");
		expect(commentCountOf("ToDo", "a")).toBe(3);
		expect(commentCountOf("ToDo", "b")).toBe(0);
	});

	it("matches a numeric row name to the starred names the read lists", () => {
		seedFavourites("Plain", { favourites: ["7"] }, [7, 8] as unknown as string[]);
		expect(isStarred("Plain", "7", "me")).toBe(true);
		expect(isStarred("Plain", "8", "me")).toBe(false);
	});

	it("drops a second click while the first toggle is in flight", async () => {
		seedFavourites("ToDo", { favourites: [] }, ["c"]);
		let finish = () => {};
		api.addFavourite.mockReturnValue(new Promise<void>((resolve) => (finish = resolve)));
		const first = toggleStar("ToDo", "c", "me");
		await toggleStar("ToDo", "c", "me");
		finish();
		await first;
		expect(api.addFavourite).toHaveBeenCalledTimes(1);
		expect(isStarred("ToDo", "c", "me")).toBe(true);
	});
});
