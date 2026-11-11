// A multi-line or Table MultiSelect row draws its value over several lines at rest, so opening it never resizes it; Esc truly cancels.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, onBeforeUnmount, ref } from "vue";

vi.mock("frappe-ui", () => ({
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
	frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
	runMethod: vi.fn(async () => ({ data: null })),
	getMeta: vi.fn(async () => ({ data: null })),
}));

import { CommitKey, DocKey, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelField from "../PanelField.vue";
import { PanelContextKey } from "../context";

// Like frappe-ui's input: removing it while focused fires a `change` with its draft.
const Control = defineComponent({
	props: { panel: Boolean, modelValue: null },
	emits: ["update:modelValue", "change"],
	setup(props, { emit }) {
		onBeforeUnmount(() => emit("change", draft));
		let draft = "";
		return () =>
			h("textarea", {
				"data-control": "",
				"data-panel": props.panel,
				value: props.modelValue,
				onInput: (e: Event) => {
					draft = (e.target as HTMLTextAreaElement).value;
					emit("update:modelValue", draft);
				},
			});
	},
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function mount(field: FieldNode, doc: Record<string, any>, onDetails = true) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const update = vi.fn((name: string, value: any) => (docRef.value[name] = value));
	const commit = { pending: vi.fn(), commit: vi.fn(), discard: vi.fn() };
	const docRef = ref(doc);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field }) }));
	app.provide(DocKey, docRef);
	app.provide(UpdateKey, update);
	app.provide(CommitKey, commit as any);
	app.provide(ResolveFieldKey, () => Control);
	app.provide(PanelContextKey, { onDetails: () => onDetails } as any);
	app.mount(root);
	mounted.push(app);
	return { root, update, commit, doc: docRef };
}

const row = (root: HTMLElement, name: string) => root.querySelector<HTMLElement>(`[data-fieldname="${name}"]`)!;

describe("a Small Text, Text or Long Text row at rest", () => {
	const note: FieldNode = { fieldname: "note", fieldtype: "Text", label: "Note" };

	it("wraps its value over up to six lines, keeping line breaks", () => {
		const { root } = mount(note, { note: "one\ntwo" });
		const value = row(root, "note").querySelector("span.line-clamp-6")!;

		expect(value.textContent).toBe("one\ntwo");
		expect(value.className).toContain("whitespace-pre-wrap");
		expect(value.className).toContain("leading-5");
	});

	it("shows the placeholder in the muted colour when empty", () => {
		const { root } = mount(note, { note: "" });
		const value = row(root, "note").querySelector("span.line-clamp-6")!;

		expect(value.textContent).toBe("Add Note...");
		expect(value.className).toContain("text-ink-gray-4");
	});

	it("opens its control in panel mode", async () => {
		const { root } = mount(note, { note: "x" });

		row(root, "note").click();
		await nextTick();

		expect(root.querySelector("[data-control]")!.getAttribute("data-panel")).toBe("true");
	});
});

describe("a heavy field that Details does not draw", () => {
	it("opens in place with no panel look", async () => {
		const code: FieldNode = { fieldname: "code", fieldtype: "Code", label: "Code" };
		const { root } = mount(code, { code: "x" }, false);

		row(root, "code").click();
		await nextTick();

		expect(root.querySelector("[data-control]")!.getAttribute("data-panel")).toBe("false");
	});
});

describe("a Table MultiSelect row at rest", () => {
	const tags = {
		fieldname: "tags",
		fieldtype: "Table MultiSelect",
		label: "Tags",
		options: "Tag Link",
		childFields: [{ fieldname: "tag", fieldtype: "Link", options: "Tag", label: "Tag" }],
	} as FieldNode;

	it("draws one chip per link with a held, invisible ×, in a lane that keeps the × and chevron space", () => {
		const { root } = mount(tags, { tags: [{ tag: "Red" }, { tag: "Blue" }] });
		const cell = row(root, "tags");
		const chips = cell.querySelectorAll("span.h-5");

		expect([...chips].map((chip) => chip.textContent!.trim())).toEqual(["Red", "Blue"]);
		expect(cell.querySelectorAll('[role="button"].invisible')).toHaveLength(2);
		expect(cell.className).toContain("pe-[30px]");
	});

	it("shows the placeholder when nothing is selected", () => {
		const { root } = mount(tags, { tags: [] });

		expect(row(root, "tags").textContent).toContain("Add Tags...");
	});

	it("keeps the child table error visible in the row, and stays closed, when the Link field is missing", async () => {
		const bare = { ...tags, childFields: [] } as FieldNode;
		const { root } = mount(bare, { tags: [] });

		expect(row(root, "tags").textContent).toContain("Child table metadata unavailable");
		row(root, "tags").click();
		await nextTick();

		expect(root.querySelector("[data-control]")).toBeNull();
	});

	it("does not show it when the Link field is there", () => {
		const { root } = mount(tags, { tags: [] });

		expect(row(root, "tags").textContent).not.toContain("metadata unavailable");
	});
});

describe("Esc in an open row", () => {
	const note: FieldNode = { fieldname: "note", fieldtype: "Text", label: "Note" };

	it("puts the opening value back and does not commit the draft the removed input emits", async () => {
		const { root, update, commit, doc } = mount(note, { note: "before" });
		row(root, "note").click();
		await nextTick();
		const control = root.querySelector<HTMLTextAreaElement>("[data-control]")!;
		control.value = "draft";
		control.dispatchEvent(new Event("input"));
		await nextTick();

		control.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await nextTick();

		expect(root.querySelector("[data-control]")).toBeNull();
		expect(doc.value.note).toBe("before");
		expect(update).toHaveBeenLastCalledWith("note", "before");
		expect(commit.commit).not.toHaveBeenCalled();
	});

	it("drops the commit channel's pending edit, so a save cannot fire the handler with the draft", async () => {
		const { root, commit } = mount(note, { note: "before" });
		row(root, "note").click();
		await nextTick();
		const control = root.querySelector<HTMLTextAreaElement>("[data-control]")!;
		control.value = "draft";
		control.dispatchEvent(new Event("input"));
		await nextTick();
		expect(commit.pending).toHaveBeenCalledWith("note", "draft");

		control.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await nextTick();

		expect(commit.discard).toHaveBeenCalledWith("note");
	});

	it("lets the next open edit again", async () => {
		const { root, update, doc } = mount(note, { note: "before" });
		row(root, "note").click();
		await nextTick();
		root.querySelector("[data-control]")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await nextTick();

		row(root, "note").click();
		await nextTick();
		const control = root.querySelector<HTMLTextAreaElement>("[data-control]")!;
		control.value = "after";
		control.dispatchEvent(new Event("input"));

		expect(update).toHaveBeenLastCalledWith("note", "after");
		expect(doc.value.note).toBe("after");
	});
});
