// The `doctype_update` listener as claims: it forgets the changed DocType's meta, form layouts and
// list settings, and nothing else; an open page keeps what it holds.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const fake = vi.hoisted(() => ({ getMeta: vi.fn(), runMethod: vi.fn(), version: 0 }));

vi.mock("@framework/ui/api", () => ({ getMeta: fake.getMeta, runMethod: fake.runMethod }));
vi.mock("@framework/ui/composables/useDocPermissions", () => ({
	useDocPermissions: () => ({ fieldAccess: () => "write" }),
}));

import { resetDoctypeMeta, useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetFormLayouts, useFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";
import { resetListSettings, useListSettings } from "@/list/useListSettings";
import { watchDoctypeUpdates } from "../doctypeUpdates";

const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const GET_LIST_SETTINGS = "frappe.desk.doctype.doctype_view.api.get";

type Handler = (...args: unknown[]) => void;
const socket = {
	handlers: new Map<string, Handler[]>(),
	emit() {},
	on(event: string, handler: Handler) {
		socket.handlers.set(event, [...(socket.handlers.get(event) ?? []), handler]);
	},
	off(event: string, handler: Handler) {
		socket.handlers.set(event, (socket.handlers.get(event) ?? []).filter((one) => one !== handler));
	},
	fire(...args: unknown[]) {
		for (const handler of socket.handlers.get("doctype_update") ?? []) handler(...args);
	},
};

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await Promise.resolve();
		await nextTick();
	}
}

function warm(doctype: string) {
	useDoctypeMeta(doctype);
	useFormLayout({ doctype, type: "Details" });
	useFormLayout({ doctype, type: "Side Panel" });
	useListSettings(doctype);
}

function fetched() {
	const metas = fake.getMeta.mock.calls.map(([doctype]) => `meta ${doctype}`);
	const reads = fake.runMethod.mock.calls.map(([method, args]) => {
		if (method === GET_FORM_LAYOUTS) return `layout ${args.dt}:${args.type}`;
		if (method === GET_LIST_SETTINGS) return `settings ${args.doctype}`;
		return method;
	});
	return [...metas, ...reads];
}

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	resetListSettings();
	socket.handlers.clear();
	fake.version = 0;
	fake.getMeta.mockReset().mockImplementation(async (doctype: string) => ({
		data: { name: doctype, fields: [], version: ++fake.version },
		children: doctype === "Sales Order" ? [{ name: "Sales Order Item", fields: [] }] : [],
	}));
	fake.runMethod.mockReset().mockResolvedValue({ data: null });
});

describe("watchDoctypeUpdates", () => {
	it("drops each memo of the changed DocType and no other", async () => {
		watchDoctypeUpdates(socket);
		warm("Lead");
		warm("Deal");
		await settle();
		fake.getMeta.mockClear();
		fake.runMethod.mockClear();
		socket.fire({ doctype: "Lead" });
		warm("Lead");
		warm("Deal");
		await settle();
		expect(fetched().sort()).toEqual([
			"layout Lead:Details",
			"layout Lead:Side Panel",
			"meta Lead",
			"settings Lead",
		]);
	});

	it("drops the meta of a DocType that holds the changed one as a child table", async () => {
		watchDoctypeUpdates(socket);
		useDoctypeMeta("Sales Order");
		await settle();
		socket.fire({ doctype: "Sales Order Item" });
		useDoctypeMeta("Sales Order");
		expect(fake.getMeta).toHaveBeenCalledTimes(2);
	});

	it("fetches again for a later caller while an earlier handle keeps the meta it read", async () => {
		watchDoctypeUpdates(socket);
		const before = useDoctypeMeta("Lead");
		await settle();
		expect(before.meta.value).toMatchObject({ version: 1 });
		socket.fire({ doctype: "Lead" });
		const after = useDoctypeMeta("Lead");
		await settle();
		expect(after.meta.value).toMatchObject({ version: 2 });
		expect(before.meta.value).toMatchObject({ version: 1 });
	});

	it("drops nothing for a payload without a DocType name", async () => {
		watchDoctypeUpdates(socket);
		warm("Lead");
		await settle();
		for (const payload of [undefined, null, "Lead", {}, { doctype: "" }, { doctype: 7 }]) {
			socket.fire(payload);
		}
		warm("Lead");
		await settle();
		expect(fetched()).toHaveLength(4);
	});

	it("drops nothing once stopped", async () => {
		const stop = watchDoctypeUpdates(socket);
		useDoctypeMeta("Lead");
		stop();
		socket.fire({ doctype: "Lead" });
		useDoctypeMeta("Lead");
		expect(fake.getMeta).toHaveBeenCalledTimes(1);
	});
});
