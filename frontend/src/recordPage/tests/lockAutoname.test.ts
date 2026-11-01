// A saved record's `field:` autoname field reads only; a new record's stays editable.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const fake = vi.hoisted(() => ({ getMeta: vi.fn(), runMethod: vi.fn(), access: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ getMeta: fake.getMeta, runMethod: fake.runMethod }));
vi.mock("@framework/ui/useDocPermissions", () => ({
	useDocPermissions: () => ({ fieldAccess: fake.access }),
}));

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetFormLayouts, useFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";

const FIELDS = [
	{ fieldname: "salutation", fieldtype: "Data", label: "Salutation", reqd: 1 },
	{ fieldname: "title", fieldtype: "Data", label: "Title" },
];
const TREE = [{ name: "details", label: "Details", sections: [{ columns: [{ fields: ["salutation", "title"] }] }] }];

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await Promise.resolve();
		await nextTick();
	}
}

async function readOnlyFields(autoname: string | undefined, lockAutoname: boolean | undefined) {
	fake.getMeta.mockResolvedValue({ data: { name: "Salutation", autoname, fields: FIELDS }, children: [] });
	const { layout } = useFormLayout({ doctype: "Salutation", type: "Details", fallback: "meta", lockAutoname });
	await settle();
	const nodes: any[] = [];
	const walk = (value: any) => {
		if (Array.isArray(value)) return value.forEach(walk);
		if (!value || typeof value !== "object") return;
		if (value.fieldname) nodes.push(value);
		Object.values(value).forEach(walk);
	};
	walk(layout.value);
	return Object.fromEntries(nodes.map((node) => [node.fieldname, Boolean(node.readOnly)]));
}

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	fake.getMeta.mockReset();
	fake.access.mockReset().mockReturnValue("write");
	fake.runMethod.mockReset().mockResolvedValue({ data: { layouts: [], fallback: TREE } });
});

describe("lockAutoname", () => {
	it("makes the field a `field:` rule names read-only", async () => {
		expect(await readOnlyFields("field:salutation", true)).toEqual({ salutation: true, title: false });
	});

	it("reads the rule without case or padding", async () => {
		expect(await readOnlyFields("Field: salutation ", true)).toEqual({ salutation: true, title: false });
	});

	it("leaves it editable on a new record", async () => {
		expect(await readOnlyFields("field:salutation", undefined)).toEqual({ salutation: false, title: false });
	});

	it.each([undefined, "prompt", "hash", "field:", "format:SAL-{####}"])("locks nothing under autoname %s", async (autoname) => {
		expect(await readOnlyFields(autoname, true)).toEqual({ salutation: false, title: false });
	});
});
