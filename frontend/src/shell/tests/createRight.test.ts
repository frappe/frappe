// Who may create a doctype's records, from the meta's DocPerm rows and the session.
import { describe, expect, it } from "vitest";
import type { DoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { canCreate } from "@/createRight";

const USER = { user: "test@example.com", roles: ["Sales User", "Desk User"], readOnlyMode: false };
const ADMIN = { user: "Administrator", roles: ["Administrator"], readOnlyMode: false };

function meta(overrides: Partial<DoctypeMeta> = {}): DoctypeMeta {
	return {
		name: "Lead",
		permissions: [{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 1 }],
		...overrides,
	};
}

describe("canCreate", () => {
	it("allows a role with a level 0 create row", () => {
		expect(canCreate(meta(), USER)).toBe(true);
	});

	it("reads a row with no permlevel as level 0", () => {
		expect(canCreate(meta({ permissions: [{ role: "Desk User", create: 1 }] }), USER)).toBe(true);
	});

	it("refuses when the create row belongs to a role the person lacks", () => {
		const rows = [{ role: "Sales Manager", permlevel: 0, create: 1 }];
		expect(canCreate(meta({ permissions: rows }), USER)).toBe(false);
	});

	it("refuses a role that may read and write but not create", () => {
		const rows = [{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 0 }];
		expect(canCreate(meta({ permissions: rows }), USER)).toBe(false);
	});

	it("refuses a create row above level 0", () => {
		const rows = [{ role: "Sales User", permlevel: 1, create: 1 }];
		expect(canCreate(meta({ permissions: rows }), USER)).toBe(false);
	});

	it("refuses a meta with no permission rows", () => {
		expect(canCreate(meta({ permissions: undefined }), USER)).toBe(false);
	});

	it("allows Administrator without any row", () => {
		expect(canCreate(meta({ permissions: [] }), ADMIN)).toBe(true);
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
