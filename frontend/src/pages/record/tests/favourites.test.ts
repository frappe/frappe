// The `favourites` rows of docinfo, as the star and its card read them.
import { describe, expect, it } from "vitest";
import { favouritesOf, hasFavourited } from "../favourites";

const docinfo = {
	favourites: [{ user: "ann@example.com" }, { user: "me@example.com" }, { user: "bob@example.com" }],
	users: { "ann@example.com": { full_name: "Ann", user_image: "/ann.png" } },
};

describe("favouritesOf", () => {
	it("puts the reader first as You, and names the rest from the users part", () => {
		expect(favouritesOf(docinfo, "me@example.com")).toEqual([
			{ id: "me@example.com", name: "You" },
			{ id: "ann@example.com", name: "Ann", image: "/ann.png" },
			{ id: "bob@example.com", name: "bob@example.com", image: undefined },
		]);
	});

	it("is nobody without the bucket, and never reads the likes", () => {
		expect(favouritesOf(null, "me@example.com")).toEqual([]);
		expect(favouritesOf({}, "me@example.com")).toEqual([]);
		expect(favouritesOf({ _liked_by: '["me@example.com"]' } as any, "me@example.com")).toEqual([]);
	});

	it("says whether the reader is among them", () => {
		expect(hasFavourited(docinfo, "ann@example.com")).toBe(true);
		expect(hasFavourited(docinfo, "zed@example.com")).toBe(false);
		expect(hasFavourited(null, "ann@example.com")).toBe(false);
	});
});
