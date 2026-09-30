// What the `doctype_update` listener promises: it marks the changed DocType's meta, form layouts
// and list settings stale, and nothing else; an open page keeps what it holds.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const fake = vi.hoisted(() => ({ getMeta: vi.fn(), runMethod: vi.fn(), version: 0 }));

vi.mock("@framework/ui/api", () => ({ getMeta: fake.getMeta, runMethod: fake.runMethod }));
vi.mock("@framework/ui/composables/useDocPermissions", () => ({
	useDocPermissions: () => ({ fieldAccess: () => "write" }),
}));

import { resetDoctypeMeta, useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { holdFresh } from "@framework/ui/utils/sharedState";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
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
	it("reads each memo of the changed DocType again, and no other", async () => {
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

	it("reads again the meta of a DocType that holds the changed one as a child table", async () => {
		watchDoctypeUpdates(socket);
		useDoctypeMeta("Sales Order");
		await settle();
		socket.fire({ doctype: "Sales Order Item" });
		useDoctypeMeta("Sales Order");
		expect(fake.getMeta).toHaveBeenCalledTimes(2);
	});

	it("shows a later caller the old meta, then the new one, while an earlier handle keeps the old", async () => {
		watchDoctypeUpdates(socket);
		const before = useDoctypeMeta("Lead");
		await settle();
		expect(before.meta.value).toMatchObject({ version: 1 });
		socket.fire({ doctype: "Lead" });
		const after = useDoctypeMeta("Lead");
		expect(after.meta.value).toMatchObject({ version: 1 });
		expect(after.loading.value).toBe(false);
		await settle();
		expect(after.meta.value).toMatchObject({ version: 2 });
		expect(before.meta.value).toMatchObject({ version: 1 });
	});

	it("marks nothing for a payload without a DocType name", async () => {
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

	it("marks nothing once stopped", async () => {
		const stop = watchDoctypeUpdates(socket);
		useDoctypeMeta("Lead");
		stop();
		socket.fire({ doctype: "Lead" });
		useDoctypeMeta("Lead");
		expect(fake.getMeta).toHaveBeenCalledTimes(1);
	});
});

describe("a form layout after the DocType changes", () => {
	const DETAILS = { doctype: "Lead", type: "Details" } as const;
	let rows: ReturnType<typeof deferred<unknown>>;

	function layoutOf(fields: string[]) {
		return { data: { layouts: [], fallback: [{ sections: [{ columns: [{ fields }] }] }] } };
	}

	function fieldnames(layout: FormLayoutSchema) {
		return layout.flatMap((tab) =>
			tab.sections.flatMap((section) => section.columns.flatMap((column) => column.fields.map((field) => field.fieldname)))
		);
	}

	async function markedAfter(fields: string[]) {
		fake.getMeta.mockImplementation(async (doctype: string) => ({
			data: {
				name: doctype,
				fields: [
					{ fieldname: "title", fieldtype: "Data", label: "Title" },
					{ fieldname: "amount", fieldtype: "Currency", label: "Amount" },
				],
			},
		}));
		fake.runMethod.mockResolvedValueOnce(layoutOf(fields));
		const before = useFormLayout(DETAILS);
		await settle();
		watchDoctypeUpdates(socket);
		socket.fire({ doctype: "Lead" });
		rows = deferred();
		fake.runMethod.mockReturnValueOnce(rows.promise);
		return before;
	}

	it("shows a later caller the old rows at once, then the fresh rows, while an earlier handle keeps the old", async () => {
		const before = await markedAfter(["title"]);
		const after = useFormLayout(DETAILS);
		expect(after.loading.value).toBe(false);
		expect(fieldnames(after.layout.value)).toEqual(["title"]);
		rows.resolve(layoutOf(["title", "amount"]));
		await after.refreshed();
		expect(fieldnames(after.layout.value)).toEqual(["title", "amount"]);
		expect(fieldnames(before.layout.value)).toEqual(["title"]);
	});

	it("settles only once the fresh rows have landed", async () => {
		await markedAfter(["title"]);
		const after = useFormLayout(DETAILS);
		let settled = false;
		void after.settled().then(() => (settled = true));
		await settle();
		expect(settled).toBe(false);
		rows.resolve(layoutOf(["title", "amount"]));
		await settle();
		expect(settled).toBe(true);
		expect(fieldnames(after.layout.value)).toEqual(["title", "amount"]);
	});

	it("resolves refreshed once the fresh rows and meta arrive, and shows them when the hold is released", async () => {
		await markedAfter(["title"]);
		const release = holdFresh();
		const after = useFormLayout(DETAILS);
		rows.resolve(layoutOf(["title", "amount"]));
		await after.refreshed();
		expect(fieldnames(after.layout.value)).toEqual(["title"]);
		release();
		await nextTick();
		expect(fieldnames(after.layout.value)).toEqual(["title", "amount"]);
	});

	it("keeps the old rows without an error when the fresh read fails", async () => {
		await markedAfter(["title"]);
		const after = useFormLayout(DETAILS);
		rows.reject(new Error("Network down"));
		await after.refreshed();
		await after.settled();
		expect(after.error.value).toBeNull();
		expect(fieldnames(after.layout.value)).toEqual(["title"]);
	});

	it("reads again for the next caller after a failed fresh read", async () => {
		await markedAfter(["title"]);
		rows.reject(new Error("Network down"));
		await useFormLayout(DETAILS).refreshed();

		fake.runMethod.mockResolvedValueOnce(layoutOf(["title", "amount"]));
		const next = useFormLayout(DETAILS);
		expect(fieldnames(next.layout.value)).toEqual(["title"]);
		await next.settled();
		expect(fieldnames(next.layout.value)).toEqual(["title", "amount"]);
	});
});

function deferred<Value>() {
	let resolve!: (value: Value) => void;
	let reject!: (reason: unknown) => void;
	const promise = new Promise<Value>((done, fail) => {
		resolve = done;
		reject = fail;
	});
	return { promise, resolve, reject };
}
