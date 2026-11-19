// The layout read names the shell's app, so the server can let that app's rows replace the unnamed ones.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const fake = vi.hoisted(() => ({ getMeta: vi.fn(), runMethod: vi.fn() }));

vi.mock("@framework/ui/api", () => ({ getMeta: fake.getMeta, runMethod: fake.runMethod }));
vi.mock("@framework/ui/useDocPermissions", () => ({
	useDocPermissions: () => ({ fieldAccess: () => "write" }),
}));

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import {
	resetFormLayouts,
	setFormLayoutApp,
	useFormLayout,
} from "@/recordPage/formLayoutSource/useFormLayout";

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await Promise.resolve();
		await nextTick();
	}
}

function sentArgs() {
	return fake.runMethod.mock.calls.map(([, args]) => args);
}

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	fake.getMeta.mockReset().mockResolvedValue({ data: { name: "Contact", fields: [] }, children: [] });
	fake.runMethod.mockReset().mockResolvedValue({ data: null });
});

afterEach(() => setFormLayoutApp(null));

describe("setFormLayoutApp", () => {
	it("sends the shell's app with each layout read", async () => {
		setFormLayoutApp("crm");
		useFormLayout({ doctype: "Contact", type: "Side Panel" });
		await settle();
		expect(sentArgs()).toEqual([{ dt: "Contact", type: "Side Panel", app: "crm" }]);
	});

	it("sends no app on the index, where only rows naming none apply", async () => {
		setFormLayoutApp(null);
		useFormLayout({ doctype: "Contact", type: "Side Panel" });
		await settle();
		expect(sentArgs()).toEqual([{ dt: "Contact", type: "Side Panel" }]);
	});
});
