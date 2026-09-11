// The people editors on the panel: gated by the record's rights, each pick one write through
// `page.call`, and the sidecar re-read after it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

// The pickers are stubbed to their trigger: `pick` stands in for a selection made inside.
const stub = vi.hoisted(() => ({ nextPick: [] as string[] | string, nextQuery: "" }));

vi.mock("frappe-ui", () => {
	const Picker = defineComponent({
		emits: ["update:modelValue", "update:query", "update:open"],
		setup(_, { slots, emit }) {
			return () =>
				h("div", { "data-picker": "" }, [
					slots.trigger?.({ open: false }),
					h("button", {
						"data-pick": "",
						onClick: () => {
							emit("update:query", stub.nextQuery);
							emit("update:modelValue", stub.nextPick);
						},
					}),
					slots.footer?.({}),
				]);
		},
	});
	const Plain = (tag: string) =>
		defineComponent({ setup: (_, { slots }) => () => h(tag, slots.default?.()) });
	return {
		MultiSelect: Picker,
		Combobox: Picker,
		Avatar: defineComponent({
			props: ["label"],
			setup: (props) => () => h("span", { "data-avatar": props.label }),
		}),
		Tooltip: Plain("span"),
		Button: defineComponent({
			props: ["label"],
			setup: (props, { slots }) => () => h("button", slots.default?.() ?? props.label),
		}),
	};
});

import { PanelContextKey, type DocInfo } from "../context";
import PeopleAvatars from "../PeopleAvatars.vue";
import QuickActions from "../QuickActions.vue";
import RecordIdentity from "../RecordIdentity.vue";
import RecordPeople from "../RecordPeople.vue";
import ShareDialog from "../ShareDialog.vue";

const mounted: ReturnType<typeof createApp>[] = [];
// What `page.quickActions.visible()` answers; only the tag action's rendering is tested here.
const quickActions: any[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	stub.nextPick = [];
	stub.nextQuery = "";
	quickActions.splice(0);
});

function setup(info: DocInfo, component: any = RecordPeople, props: Record<string, any> = {}) {
	const page = {
		call: vi.fn(async () => null),
		toast: { error: vi.fn() },
		dialog: { open: vi.fn(async () => null) },
	};
	const docinfo = ref<DocInfo | null>(info);
	const reloadDocinfo = vi.fn(async () => {});
	const context = {
		doctype: "CRM Deal",
		docname: "D-1",
		doc: ref({}),
		meta: ref(null),
		docinfo,
		controller: { page, quickActions: { visible: () => quickActions } } as any,
		run: vi.fn(),
		reloadDocinfo,
	};
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(component, props) }));
	app.provide(PanelContextKey, context);
	app.mount(root);
	mounted.push(app);
	return { root, page, reloadDocinfo, docinfo, context };
}

const info = (permissions: Record<string, 0 | 1>): DocInfo => ({
	assignments: [{ owner: "ann@example.com" }],
	shared: [{ user: "bob@example.com" }],
	tags: "urgent",
	user_info: { "ann@example.com": { fullname: "Ann" }, "bob@example.com": { fullname: "Bob" } },
	permissions,
});

async function pick(root: HTMLElement, values: string[] | string, query = "") {
	stub.nextPick = values;
	stub.nextQuery = query;
	root.querySelector<HTMLElement>("[data-pick]")!.click();
	await nextTick();
}

describe("the gate", () => {
	it("edits assignees and shares with the write and share rights", () => {
		const { root } = setup(info({ write: 1, share: 1 }));
		expect(root.querySelector("[data-assign]")).not.toBeNull();
		expect(root.querySelector("[data-share]")).not.toBeNull();
	});

	it("reads the rows without them, and still names the people", () => {
		const { root } = setup(info({ read: 1 }));
		expect(root.querySelector("[data-assign]")).toBeNull();
		expect(root.querySelector("[data-share]")).toBeNull();
		expect(root.textContent).toContain("Ann");
		expect(root.textContent).toContain("Bob");
	});

	it("says so when nobody is assigned or shared", () => {
		const { root } = setup({ permissions: { read: 1 } });
		expect(root.textContent).toContain("Not assigned");
		expect(root.textContent).toContain("Not shared");
	});
});

describe("assigning", () => {
	it("adds who the pick added, drops who it dropped, and re-reads the sidecar after each", async () => {
		const { root, page, reloadDocinfo } = setup(info({ write: 1 }));
		await pick(root, ["cy@example.com"]);
		await vi.waitFor(() => expect(reloadDocinfo).toHaveBeenCalledTimes(2));
		expect(page.call).toHaveBeenCalledWith("frappe.desk.form.assign_to.add", {
			doctype: "CRM Deal",
			name: "D-1",
			assign_to: ["cy@example.com"],
		});
		expect(page.call).toHaveBeenCalledWith("frappe.desk.form.assign_to.remove", {
			doctype: "CRM Deal",
			name: "D-1",
			assign_to: "ann@example.com",
		});
		const callOrder = page.call.mock.invocationCallOrder[0];
		expect(reloadDocinfo.mock.invocationCallOrder[0]).toBeGreaterThan(callOrder);
	});

	it("toasts a refused write and leaves the sidecar alone", async () => {
		const { root, page, reloadDocinfo } = setup(info({ write: 1 }));
		page.call.mockRejectedValueOnce({ messages: ["Not permitted"] });
		await pick(root, ["ann@example.com", "cy@example.com"]);
		await vi.waitFor(() => expect(page.toast.error).toHaveBeenCalledWith("Not permitted"));
		expect(reloadDocinfo).not.toHaveBeenCalled();
	});
});

describe("sharing", () => {
	it("opens the share dialog on the page's own stack, handed the live context", async () => {
		const { root, page, docinfo } = setup(info({ share: 1 }));
		root.querySelector<HTMLElement>("[data-share]")!.click();
		expect(page.dialog.open).toHaveBeenCalledTimes(1);
		const [component, props, options] = page.dialog.open.mock.calls[0] as any[];
		expect(component).toBeTruthy();
		expect(props.context.docinfo).toBe(docinfo);
		expect(options).toEqual({ title: "Share this record" });
	});
});

describe("the share dialog", () => {
	// The dialog acts on the panel's context, so the assertions read the host's page.
	function open(info: DocInfo) {
		const host = setup(info);
		const { root } = setup(info, ShareDialog, { context: host.context, close: vi.fn() });
		return { root, page: host.page, context: host.context, docinfo: host.docinfo };
	}

	it("shares with read and write on a pick, and re-reads the sidecar", async () => {
		const { root, page, context } = open(info({ share: 1 }));
		await pick(root, "cy@example.com");
		await vi.waitFor(() => expect(context.reloadDocinfo).toHaveBeenCalledTimes(1));
		expect(page.call).toHaveBeenCalledWith("frappe.share.add", {
			doctype: "CRM Deal",
			name: "D-1",
			user: "cy@example.com",
			read: 1,
			write: 1,
		});
	});

	it("stops a share by dropping read, for a person and for everyone", async () => {
		const shared = info({ share: 1 });
		shared.shared = [{ user: "bob@example.com", write: 1 }, { user: "", everyone: 1 }];
		const { root, page, context } = open(shared);
		expect(root.textContent).toContain("Can edit");
		root.querySelector<HTMLElement>("[aria-label='Stop sharing with Bob']")!.click();
		root.querySelector<HTMLElement>("[aria-label='Stop sharing with Everyone']")!.click();
		await vi.waitFor(() => expect(context.reloadDocinfo).toHaveBeenCalledTimes(2));
		const stop = (user: string | null, everyone: 0 | 1) => ({
			doctype: "CRM Deal",
			name: "D-1",
			user,
			permission_to: "read",
			value: 0,
			everyone,
		});
		expect(page.call).toHaveBeenCalledWith("frappe.share.set_permission", stop("bob@example.com", 0));
		expect(page.call).toHaveBeenCalledWith("frappe.share.set_permission", stop(null, 1));
	});

	it("follows the live sidecar, and says so when nobody is left", async () => {
		const { root, docinfo } = open(info({ share: 1 }));
		expect(root.querySelectorAll("[data-shared-with]")).toHaveLength(1);
		docinfo.value = { ...docinfo.value, shared: [] };
		await nextTick();
		expect(root.querySelectorAll("[data-shared-with]")).toHaveLength(0);
		expect(root.textContent).toContain("not shared with anyone");
	});
});

describe("the avatar stack", () => {
	it("shows three and counts the rest", () => {
		const people = ["a", "b", "c", "d", "e"].map((id) => ({ id, name: id }));
		const { root } = setup({}, PeopleAvatars, { people, placeholder: "Nobody" });
		expect(root.querySelectorAll("[data-avatar]")).toHaveLength(3);
		expect(root.textContent).toContain("+2");
	});
});

describe("tags", () => {
	it("draws no row until the record has a tag; the first comes from the quick action", async () => {
		const bare = setup({ permissions: { write: 1 } }, RecordIdentity);
		expect(bare.root.querySelector("[data-tags]")).toBeNull();

		quickActions.push({ name: "tags", label: "Tags", icon: "lucide-tag", tagging: true });
		const { root, page, reloadDocinfo } = setup({ permissions: { write: 1 } }, QuickActions);
		expect(root.textContent).toContain("Tags");
		await pick(root, ["first"], "first");
		await vi.waitFor(() => expect(reloadDocinfo).toHaveBeenCalledTimes(1));
		expect(page.call).toHaveBeenCalledWith("frappe.desk.doctype.tag.tag.add_tag", {
			tag: "first",
			dt: "CRM Deal",
			dn: "D-1",
		});
	});

	it("draws the chips read-only for a reader who may not write", () => {
		const tagged = setup(info({ read: 1 }), RecordIdentity);
		expect(tagged.root.textContent).toContain("urgent");
		expect(tagged.root.querySelector("[data-add-tag]")).toBeNull();
		expect(tagged.root.querySelector("[aria-label='Remove urgent']")).toBeNull();
	});

	it("removes a tag from its chip and adds one the picker created", async () => {
		const { root, page, reloadDocinfo } = setup(info({ write: 1 }), RecordIdentity);
		root.querySelector<HTMLElement>("[aria-label='Remove urgent']")!.click();
		await vi.waitFor(() => expect(reloadDocinfo).toHaveBeenCalledTimes(1));
		expect(page.call).toHaveBeenCalledWith("frappe.desk.doctype.tag.tag.remove_tag", {
			tag: "urgent",
			dt: "CRM Deal",
			dn: "D-1",
		});

		await pick(root, ["urgent"], "later");
		root.querySelector<HTMLElement>("[data-create-tag]")!.click();
		await vi.waitFor(() => expect(reloadDocinfo).toHaveBeenCalledTimes(2));
		expect(page.call).toHaveBeenCalledWith("frappe.desk.doctype.tag.tag.add_tag", {
			tag: "later",
			dt: "CRM Deal",
			dn: "D-1",
		});
	});
});
