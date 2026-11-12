import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useBulkCollaboration, type BulkTarget } from "../bulkCollaboration";
import { callsFor, scopeText } from "../collabCalls";

const meta = ref<Record<string, unknown> | null>({ track_changes: 1, track_seen: 1 });
vi.mock("@framework/ui/useDoctypeMeta", () => ({ useDoctypeMeta: () => ({ meta }) }));

const target = (): BulkTarget => ({
	selection: { names: ["A", "B"] },
	count: 2,
	all: false,
	approx: false,
});

describe("scopeText", () => {
	it("names the selected records, or all the matching ones", () => {
		expect(scopeText({ count: 1, all: false, approx: false })).toBe("1 selected record");
		expect(scopeText({ count: 12, all: false, approx: false })).toBe("12 selected records");
		expect(scopeText({ count: 340, all: true, approx: false })).toBe("all 340 matching records");
		expect(scopeText({ count: 10000, all: true, approx: true })).toBe("all 10000+ matching records");
	});
});

describe("callsFor", () => {
	it("makes one assignment call per user and one share call per user with the edit right", () => {
		expect(callsFor("assign", { users: ["a@x", "b@x"] })).toEqual([
			{ part: "assignments", method: "POST", bodies: [{ user: "a@x" }, { user: "b@x" }] },
		]);
		expect(callsFor("share", { users: ["a@x"], canWrite: true })[0].bodies).toEqual([
			{ user: "a@x", write: 1 },
		]);
	});

	it("sends a new tag's colour, and removes by tag", () => {
		const input = { tags: ["hot", "cold"], colors: { hot: "red" } };
		expect(callsFor("add_tags", input)[0].bodies).toEqual([{ tag: "hot", color: "red" }, { tag: "cold" }]);
		expect(callsFor("remove_tags", input)[0]).toMatchObject({ method: "DELETE", part: "tags" });
	});

	it("maps the one-call kinds to their part and verb", () => {
		const call = (kind: Parameters<typeof callsFor>[0]) => {
			const [{ part, method }] = callsFor(kind, {});
			return `${method} ${part}`;
		};
		expect(call("clear_assignment")).toBe("DELETE assignments");
		expect(call("apply_assignment_rule")).toBe("POST assignment_rule");
		expect(call("follow")).toBe("POST follows");
		expect(call("unfollow")).toBe("DELETE follows");
		expect(call("mark_seen")).toBe("POST seen");
		expect(call("mark_unseen")).toBe("DELETE seen");
	});
});

describe("useBulkCollaboration", () => {
	const items = () => useBulkCollaboration("Note", target, "jane@example.com").items();
	const shown = (name: string) => {
		const item = items().find((one) => one.name === name)!;
		return item.when ? item.when({} as never) : true;
	};

	it("gates follow on track_changes and seen on track_seen", () => {
		expect([shown("follow"), shown("unfollow"), shown("mark_seen"), shown("mark_unseen")]).toEqual([
			true,
			true,
			true,
			true,
		]);
		meta.value = { track_changes: 0, track_seen: 1, issingle: 1 };
		expect([shown("follow"), shown("mark_seen")]).toEqual([false, false]);
		meta.value = { track_changes: 1, track_seen: 0 };
		expect([shown("follow"), shown("mark_seen")]).toEqual([true, false]);
	});

	it("hides follow where the server never follows: ToDo, a log type, Administrator", () => {
		const followShown = (doctype: string, user: string) => {
			const item = useBulkCollaboration(doctype, target, user)
				.items()
				.find((one) => one.name === "follow")!;
			return item.when!({} as never);
		};
		expect(followShown("Note", "jane@example.com")).toBe(true);
		expect(followShown("ToDo", "jane@example.com")).toBe(false);
		expect(followShown("Activity Log", "jane@example.com")).toBe(false);
		expect(followShown("Note", "Administrator")).toBe(false);
		meta.value = { track_changes: 0, track_seen: 1 };
		expect(followShown("Note", "jane@example.com")).toBe(false);
		meta.value = { track_changes: 1, track_seen: 1 };
	});

	it("asks each item's right and opens the dialog with the target frozen at the click", () => {
		const collab = useBulkCollaboration("Note", target, "jane@example.com");
		const rights = Object.fromEntries(collab.items().map((item) => [item.name, item.right]));
		expect(rights).toMatchObject({ assign: "write", add_tags: "write", share: "share", follow: "read" });
		collab.items().find((item) => item.name === "share")!.run!({} as never);
		expect(collab.request.value).toMatchObject({ kind: "share", count: 2, selection: { names: ["A", "B"] } });
	});
});
