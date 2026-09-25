// A background re-read merged into the draft: untouched fields follow the server, touched ones stay the reader's.
import { describe, expect, it } from "vitest";
import { mergeRefetch } from "../refetchMerge";

const OLD = "2026-09-25 10:00:00.000000";
const NEW = "2026-09-25 11:00:00.000000";

function draft(saved: Record<string, any>, edits: Record<string, any> = {}) {
	return { saved, doc: { ...JSON.parse(JSON.stringify(saved)), ...edits } };
}

describe("mergeRefetch", () => {
	it("replaces both sides of a clean page with the server's document", () => {
		const fresh = { name: "D-1", modified: NEW, status: "Won", items: [{ qty: 2 }] };

		const merged = mergeRefetch(draft({ name: "D-1", modified: OLD, status: "Open" }), fresh);

		expect(merged).toEqual({ saved: fresh, doc: fresh });
		expect(merged.doc.items).not.toBe(fresh.items);
		expect(JSON.stringify(merged.doc)).toBe(JSON.stringify(merged.saved));
	});

	it("brings an untouched field in under an edit, and takes the new modified", () => {
		const current = draft({ name: "D-1", modified: OLD, status: "Open", note: "a" }, { note: "mine" });
		const fresh = { name: "D-1", modified: NEW, status: "Won", note: "a" };

		const merged = mergeRefetch(current, fresh);

		expect(merged.saved).toEqual(fresh);
		expect(merged.doc).toEqual({ name: "D-1", modified: NEW, status: "Won", note: "mine" });
	});

	it("keeps a touched field the server also changed, and the old modified on both sides", () => {
		const current = draft({ name: "D-1", modified: OLD, status: "Open", note: "a" }, { note: "mine" });
		const fresh = { name: "D-1", modified: NEW, status: "Won", note: "theirs" };

		const merged = mergeRefetch(current, fresh);

		expect(merged.saved).toEqual({ ...fresh, modified: OLD });
		expect(merged.doc).toEqual({ name: "D-1", modified: OLD, status: "Won", note: "mine" });
	});

	it("counts a child table as one field", () => {
		const saved = { name: "D-1", modified: OLD, items: [{ qty: 1 }, { qty: 2 }] };
		const current = draft(saved, { items: [{ qty: 1 }, { qty: 5 }] });
		const fresh = { name: "D-1", modified: NEW, items: [{ qty: 9 }, { qty: 2 }] };

		const merged = mergeRefetch(current, fresh);

		expect(merged.doc.items).toEqual([{ qty: 1 }, { qty: 5 }]);
		expect(merged.doc.modified).toBe(OLD);
	});

	it("keeps a field the reader added and drops one the server no longer sends", () => {
		const current = draft({ name: "D-1", modified: OLD, gone: "x" }, { added: "mine" });

		const merged = mergeRefetch(current, { name: "D-1", modified: NEW });

		expect(merged.doc).toEqual({ name: "D-1", modified: NEW, added: "mine" });
	});

	it("hands back the same objects when the server's document is unchanged", () => {
		const current = draft({ name: "D-1", modified: OLD, status: "Open" }, { status: "Won" });

		const merged = mergeRefetch(current, { name: "D-1", modified: OLD, status: "Open" });

		expect(merged.doc).toBe(current.doc);
		expect(merged.saved).toBe(current.saved);
	});

	it("changes nothing when a save landed while the read was out", () => {
		const current = draft({ name: "D-1", modified: NEW, status: "Won" });

		const merged = mergeRefetch(current, { name: "D-1", modified: OLD, status: "Open" });

		expect(merged).toEqual(current);
	});
});
