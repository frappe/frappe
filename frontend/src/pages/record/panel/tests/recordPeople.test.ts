// The people editors on the panel: gated by the record's rights, each pick one write on the
// wrapper, and the answer replacing that part of the sidecar.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

// The pickers are stubbed to their trigger: `pick` stands in for a selection made inside.
const stub = vi.hoisted(() => ({ nextPick: [] as string[] | string, nextQuery: "" }));

// The wrapper's writes, each answering with the part it names.
const api = vi.hoisted(() => {
	const answer = (part: string, value: unknown) =>
		vi.fn(async () => ({ data: { [part]: value, users: { "cy@example.com": { full_name: "Cy" } } } }));
	return {
		addAssignment: answer("assignments", [{ user: "cy@example.com" }]),
		removeAssignment: answer("assignments", []),
		addShare: answer("shares", [{ user: "cy@example.com", read: 1, write: 1 }]),
		removeShare: answer("shares", []),
		runMethod: vi.fn(async (_method?: string, _args?: unknown): Promise<{ data: unknown }> => ({ data: null })),
		listDocuments: vi.fn(async () => ({ data: [] })),
		searchDocuments: vi.fn(async () => ({ data: [] })),
	};
});

vi.mock("@framework/ui/api", () => api);

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
					h("button", { "data-open": "", onClick: () => emit("update:open", true) }),
					h("button", { "data-close": "", onClick: () => emit("update:open", false) }),
					slots["item-prefix"]?.({ item: { label: "old", value: "old" } }),
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
		Popover: defineComponent({
			props: ["open"],
			emits: ["update:open"],
			setup: (props, { slots, emit }) => () =>
				h("div", [
					slots.trigger?.(),
					props.open ? slots.default?.() : null,
					props.open ? h("button", { "data-popover-away": "", onClick: () => emit("update:open", false) }) : null,
				]),
		}),
		KeyboardShortcut: Plain("kbd"),
		useKeyboardShortcut: vi.fn(),
		Tooltip: Plain("span"),
		Badge: Plain("span"),
		TooltipProvider: Plain("div"),
		Dropdown: defineComponent({
			props: ["options"],
			setup: (props, { slots }) => () =>
				h("div", { "data-dropdown": "" }, [
					slots.default?.(),
					...props.options.map((option: any) =>
						h("button", { "data-menu-row": option.label, onClick: option.onClick })
					),
				]),
		}),
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
import { mergePart } from "../peopleActions";
import ShareDialog from "../ShareDialog.vue";
import { TAG_COLORS, tagColorClass } from "@/tagColors";

const mounted: ReturnType<typeof createApp>[] = [];
// What `page.quickActions.visible()` answers; only the tag action's rendering is tested here.
const quickActions: any[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	stub.nextPick = [];
	stub.nextQuery = "";
	quickActions.splice(0);
	vi.clearAllMocks();
});

function setup(info: DocInfo, component: any = RecordPeople, props: Record<string, any> = {}) {
	const page = {
		call: vi.fn(async () => null),
		toast: { error: vi.fn() },
		dialog: { open: vi.fn(async () => null) },
	};
	const docinfo = ref<DocInfo | null>(info);
	const reloadDocinfo = vi.fn(async () => {});
	let onRecord = true;
	const context = {
		doctype: "CRM Deal",
		docname: "D-1",
		doc: ref({}),
		meta: ref(null),
		docinfo,
		controller: { page, quickActions: { visible: () => quickActions }, allows: () => true } as any,
		run: vi.fn(),
		reloadDocinfo,
		whileOnRecord: () => () => onRecord,
		onDetails: () => false,
	};
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(component, props) }));
	app.provide(PanelContextKey, context);
	app.mount(root);
	mounted.push(app);
	return { root, page, reloadDocinfo, docinfo, context, leaveRecord: () => (onRecord = false) };
}

const info = (permissions: Record<string, 0 | 1>): DocInfo => ({
	assignments: [{ user: "ann@example.com" }],
	shares: [{ user: "bob@example.com", read: 1 }],
	tags: ["urgent"],
	users: { "ann@example.com": { full_name: "Ann" }, "bob@example.com": { full_name: "Bob" } },
	permissions,
});

async function pick(root: HTMLElement, values: string[] | string, query = "") {
	stub.nextPick = values;
	stub.nextQuery = query;
	root.querySelector<HTMLElement>("[data-pick]")!.click();
	await nextTick();
}

/** A picking session: open the picker, make the picks, close it. */
async function session(root: HTMLElement, picks: () => Promise<void>) {
	root.querySelector<HTMLElement>("[data-open]")!.click();
	await nextTick();
	await picks();
	root.querySelector<HTMLElement>("[data-close]")!.click();
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
	it("adds who the pick added, drops who it dropped, and takes the answer as the row", async () => {
		const { root, docinfo, reloadDocinfo } = setup(info({ write: 1 }));
		await pick(root, ["cy@example.com"]);
		await vi.waitFor(() => expect(api.removeAssignment).toHaveBeenCalledTimes(1));
		expect(api.addAssignment).toHaveBeenCalledWith("CRM Deal", "D-1", { user: "cy@example.com" });
		expect(api.removeAssignment).toHaveBeenCalledWith("CRM Deal", "D-1", "ann@example.com");
		await vi.waitFor(() => expect(docinfo.value?.assignments).toEqual([]));
		expect(docinfo.value?.users).toMatchObject({
			"ann@example.com": { full_name: "Ann" },
			"cy@example.com": { full_name: "Cy" },
		});
		expect(docinfo.value?.shares).toEqual(info({}).shares);
		expect(reloadDocinfo).not.toHaveBeenCalled();
	});

	it("drops an answer that landed after the page moved to another record", async () => {
		const { root, docinfo, leaveRecord } = setup(info({ write: 1 }));
		leaveRecord();
		await pick(root, ["ann@example.com", "cy@example.com"]);
		await vi.waitFor(() => expect(api.addAssignment).toHaveBeenCalledTimes(1));
		expect(docinfo.value?.assignments).toEqual([{ user: "ann@example.com" }]);
	});

	it("toasts a refused write and leaves the sidecar alone", async () => {
		const { root, page, docinfo } = setup(info({ write: 1 }));
		api.addAssignment.mockRejectedValueOnce({ messages: ["Not permitted"] });
		await pick(root, ["ann@example.com", "cy@example.com"]);
		await vi.waitFor(() => expect(page.toast.error).toHaveBeenCalledWith("Not permitted"));
		expect(docinfo.value?.assignments).toEqual([{ user: "ann@example.com" }]);
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

	it("shares with read and write on a pick, and shows the answer", async () => {
		const { root, docinfo } = open(info({ share: 1 }));
		await pick(root, "cy@example.com");
		await vi.waitFor(() => expect(docinfo.value?.shares).toEqual([{ user: "cy@example.com", read: 1, write: 1 }]));
		expect(api.addShare).toHaveBeenCalledWith("CRM Deal", "D-1", {
			user: "cy@example.com",
			read: 1,
			write: 1,
		});
	});

	it("stops a share for a person and for everyone", async () => {
		const shared = info({ share: 1 });
		shared.shares = [{ user: "bob@example.com", read: 1, write: 1 }, { user: "everyone", read: 1 }];
		const { root } = open(shared);
		expect(root.textContent).toContain("Can edit");
		root.querySelector<HTMLElement>("[aria-label='Stop sharing with Bob']")!.click();
		root.querySelector<HTMLElement>("[aria-label='Stop sharing with Everyone']")!.click();
		await vi.waitFor(() => expect(api.removeShare).toHaveBeenCalledTimes(2));
		expect(api.removeShare).toHaveBeenCalledWith("CRM Deal", "D-1", "bob@example.com");
		expect(api.removeShare).toHaveBeenCalledWith("CRM Deal", "D-1", "everyone");
	});

	it("follows the live sidecar, and says so when nobody is left", async () => {
		const { root, docinfo } = open(info({ share: 1 }));
		expect(root.querySelectorAll("[data-shared-with]")).toHaveLength(1);
		docinfo.value = { ...docinfo.value, shares: [] };
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

const UPDATE = expect.stringContaining("update_record_tags");

/** What `update_record_tags` answers: the record's tags, and their colours. */
const answerTags = (tags: string[], tag_colors: Record<string, string> = {}) =>
	api.runMethod.mockResolvedValueOnce({ data: { tags, tag_colors } });

describe("tags", () => {
	it("hides the identity tags row on a record with none; the quick action adds the first in one call", async () => {
		const bare = setup({ permissions: { write: 1 } }, RecordIdentity);
		expect(bare.root.querySelector("[data-tags]")).toBeNull();

		quickActions.push({ name: "tags", label: "Tags", icon: "lucide-tag", tagging: true });
		const { root, docinfo } = setup({ permissions: { write: 1 } }, QuickActions);
		await vi.waitFor(() => expect(root.textContent).toContain("Tags"));
		answerTags(["first"]);
		await session(root, () => pick(root, ["first"], "first"));
		await vi.waitFor(() => expect(docinfo.value?.tags).toEqual(["first"]));
		expect(api.runMethod).toHaveBeenCalledWith(UPDATE, {
			dt: "CRM Deal",
			dn: "D-1",
			added: [{ tag: "first", color: undefined }],
			removed: [],
		});
	});

	it("draws the chips read-only for a reader who may not write", () => {
		const tagged = setup(info({ read: 1 }), RecordIdentity);
		expect(tagged.root.textContent).toContain("urgent");
		expect(tagged.root.querySelector("[data-add-tag]")).toBeNull();
		expect(tagged.root.querySelector("[aria-label='Remove urgent']")).toBeNull();
	});

	it("shows ticks on the chips at once, and sends the whole batch in one call when the picker closes", async () => {
		const { root, docinfo } = setup({ ...info({ write: 1 }), tags: ["urgent", "old"] }, RecordIdentity);
		answerTags(["old", "new"]);
		root.querySelector<HTMLElement>("[data-open]")!.click();
		await nextTick();
		await pick(root, ["old", "new"]);
		expect(root.querySelector("[data-tags]")!.textContent).toContain("new");
		expect(root.querySelector("[data-tags]")!.textContent).not.toContain("urgent");
		expect(api.runMethod).not.toHaveBeenCalled();
		root.querySelector<HTMLElement>("[data-close]")!.click();
		await vi.waitFor(() => expect(docinfo.value?.tags).toEqual(["old", "new"]));
		expect(api.runMethod).toHaveBeenCalledTimes(1);
		expect(api.runMethod).toHaveBeenCalledWith(UPDATE, {
			dt: "CRM Deal",
			dn: "D-1",
			added: [{ tag: "new", color: undefined }],
			removed: ["urgent"],
		});
	});

	it("keeps the tags row, and its picker, while the last tag is unticked, then drops it", async () => {
		const { root } = setup({ ...info({ write: 1 }), tags: ["old"] }, RecordIdentity);
		answerTags([]);
		root.querySelector<HTMLElement>("[data-open]")!.click();
		await nextTick();
		await pick(root, []);
		expect(root.querySelector("[data-tags] [data-open]")).not.toBeNull();
		root.querySelector<HTMLElement>("[data-close]")!.click();
		await vi.waitFor(() => expect(root.querySelector("[data-tags]")).toBeNull());
	});

	it("toasts, reloads the record and shows the server's tags again when the call fails", async () => {
		const { root, docinfo, page, reloadDocinfo } = setup({ ...info({ write: 1 }), tags: ["urgent"] }, RecordIdentity);
		api.runMethod.mockRejectedValueOnce(new Error("no"));
		await session(root, () => pick(root, ["urgent", "new"]));
		await vi.waitFor(() => expect(page.toast.error).toHaveBeenCalled());
		await vi.waitFor(() => expect(reloadDocinfo).toHaveBeenCalledTimes(1));
		expect(root.querySelector("[data-tags]")!.textContent).not.toContain("new");
		expect(docinfo.value?.tags).toEqual(["urgent"]);
	});

	it("creates a tag in the colour picked", async () => {
		const { root, docinfo } = setup({ ...info({ write: 1 }), tags: ["old"] }, RecordIdentity);
		answerTags(["old", "later"], { old: "", later: "Teal" });
		await session(root, async () => {
			await pick(root, ["__create__"], "later");
			expect(api.runMethod).not.toHaveBeenCalled();
			const teal = [...root.querySelectorAll("[data-tag-colors] button")].find((row) => row.textContent?.includes("Teal"));
			(teal as HTMLElement).click();
			await nextTick();
		});
		await vi.waitFor(() => expect(docinfo.value?.tags).toEqual(["old", "later"]));
		expect(api.runMethod).toHaveBeenCalledWith(UPDATE, {
			dt: "CRM Deal",
			dn: "D-1",
			added: [{ tag: "later", color: "Teal" }],
			removed: [],
		});
		expect(tagColorClass("later")).toBe(TAG_COLORS.Teal);
	});

	it("creates nothing when the colour step closes without a pick (Escape, click away)", async () => {
		const { root, docinfo } = setup({ ...info({ write: 1 }), tags: ["old"] }, RecordIdentity);
		await session(root, async () => {
			await pick(root, ["__create__"], "later");
			root.querySelector<HTMLElement>("[data-popover-away]")!.click();
			await nextTick();
		});
		expect(api.runMethod).not.toHaveBeenCalled();
		expect(docinfo.value?.tags).toEqual(["old"]);
	});

	it("recolours an existing tag from its dot, saving it on the Tag", async () => {
		const { root } = setup({ ...info({ write: 1 }), tags: ["old"] }, RecordIdentity);
		root.querySelector<HTMLElement>("[data-open]")!.click();
		await nextTick();
		root.querySelector<HTMLElement>("[data-recolour]")!.click();
		await nextTick();
		const blue = [...root.querySelectorAll("[data-tag-colors] button")].find((row) => row.textContent?.includes("Blue"));
		(blue as HTMLElement).click();
		await vi.waitFor(() => expect(api.runMethod).toHaveBeenCalledWith(expect.stringContaining("set_tag_color"), { tag: "old", color: "Blue" }));
		expect(tagColorClass("old")).toBe(TAG_COLORS.Blue);
	});
});

describe("mergePart", () => {
	it("replaces the named part, keeps the rest, and joins the users", () => {
		const before = info({ read: 1 });
		const after = mergePart(before, {
			favourites: [{ user: "cy@example.com" }],
			users: { "cy@example.com": { full_name: "Cy" } },
		});
		expect(after.favourites).toEqual([{ user: "cy@example.com" }]);
		expect(after.tags).toEqual(["urgent"]);
		expect(Object.keys(after.users!)).toEqual(["ann@example.com", "bob@example.com", "cy@example.com"]);
		expect(mergePart(null, { follows: true }).follows).toBe(true);
	});
});
