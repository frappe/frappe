// Who may create a doctype's records: the desk's rules over the level 0 create right.
import { describe, expect, it } from "vitest";
import type { DoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { canCreate } from "@/createRight";

const USER = { user: "test@example.com", createsAtLevel0: true, readOnlyMode: false };
const ADMIN = { user: "Administrator", createsAtLevel0: false, readOnlyMode: false };

function meta(overrides: Partial<DoctypeMeta> = {}): DoctypeMeta {
	return { name: "Lead", ...overrides };
}

describe("canCreate", () => {
	it("allows a person who holds the create right at level 0", () => {
		expect(canCreate(meta(), USER)).toBe(true);
	});

	it("refuses a person without it", () => {
		expect(canCreate(meta(), { ...USER, createsAtLevel0: false })).toBe(false);
	});

	it("allows Administrator without the right", () => {
		expect(canCreate(meta(), ADMIN)).toBe(true);
	});

	it("refuses everyone, Administrator too, in read-only mode", () => {
		expect(canCreate(meta(), { ...USER, readOnlyMode: true })).toBe(false);
		expect(canCreate(meta(), { ...ADMIN, readOnlyMode: true })).toBe(false);
	});

	it("refuses a single, a child table and a doctype that takes no new records here", () => {
		for (const flag of [{ issingle: 1 }, { istable: 1 }, { in_create: 1 }] as const) {
			expect(canCreate(meta(flag), USER)).toBe(false);
			expect(canCreate(meta(flag), ADMIN)).toBe(false);
		}
	});
});
