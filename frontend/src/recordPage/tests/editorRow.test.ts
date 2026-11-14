// The layout a record shows, named as the DocType editor names it, so "Edit layout" opens that one.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

const fake = vi.hoisted(() => ({ getMeta: vi.fn(), runMethod: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ getMeta: fake.getMeta, runMethod: fake.runMethod }));
vi.mock("@framework/ui/useDocPermissions", () => ({
	useDocPermissions: () => ({ fieldAccess: () => "write" }),
}));

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetFormLayouts, useFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";

const tree = [{ sections: [{ columns: [{ fields: [] }] }] }];
const row = (name: string | null, condition: string | null) => ({ name, condition, layout: tree });

async function shown(layouts: unknown[], doc: Record<string, any>) {
	fake.runMethod.mockResolvedValue({ data: { layouts, fallback: tree } });
	const layout = useFormLayout({ doctype: "Contact", type: "Details", doc: ref(doc) });
	for (let turn = 0; turn < 3; turn++) {
		await Promise.resolve();
		await nextTick();
	}
	return layout.editorRow.value;
}

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	fake.getMeta.mockReset().mockResolvedValue({ data: { name: "Contact", fields: [] }, children: [] });
	fake.runMethod.mockReset();
});

describe("editorRow", () => {
	it("names a matching site row by its row name", async () => {
		const rows = [row("FL-1", "doc.vip"), row("FL-2", null)];
		expect(await shown(rows, { vip: 1 })).toBe("FL-1");
	});

	it("names an app file's layout by its place among the app's layouts", async () => {
		const rows = [row(null, "doc.partner"), row(null, "doc.vip"), row(null, null)];
		expect(await shown(rows, { vip: 1 })).toBe("app:1");
	});

	it("names no app layout shown after site rows, which the editor never loads with them", async () => {
		const rows = [row("FL-1", "doc.lead"), row(null, "doc.vip"), row(null, null)];
		expect(await shown(rows, { vip: 1 })).toBeNull();
	});

	it("names a default site row too", async () => {
		expect(await shown([row("FL-1", "doc.vip"), row("FL-2", null)], {})).toBe("FL-2");
	});

	it("names the app file's default layout too", async () => {
		expect(await shown([row(null, "doc.vip"), row(null, null)], {})).toBe("app:1");
	});

	it("names nothing when the fallback shows", async () => {
		expect(await shown([], {})).toBeNull();
	});
});
