// The readouts of the rich fields: Text Editor and Markdown edit in their row like Long Text, Geolocation draws its control in place, Code, JSON, HTML Editor and Table keep ↗ Details.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, onBeforeUnmount, ref } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...((await importOriginal()) as Record<string, unknown>),
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
import { FieldErrorsKey, fieldErrorKey } from "@framework/ui/fields/types";
import PanelField from "../PanelField.vue";
import { PanelContextKey } from "../context";

// Like frappe-ui's input: removing it while focused fires a `change` with its draft.
const Control = defineComponent({
	props: { panel: Boolean, modelValue: null, errorId: String },
	emits: ["update:modelValue", "change"],
	setup(props, { emit }) {
		onBeforeUnmount(() => emit("change", draft));
		let draft = "";
		return () =>
			h("textarea", {
				"data-control": "",
				"data-panel": props.panel,
				"data-error-id": props.errorId,
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

function mount(
	field: FieldNode,
	doc: Record<string, any>,
	onDetails = true,
	onExpand = vi.fn(),
	errors: Record<string, string> = {}
) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const update = vi.fn((name: string, value: any) => (docRef.value[name] = value));
	const commit = { pending: vi.fn(), commit: vi.fn(), discard: vi.fn() };
	const docRef = ref(doc);
	const app = createApp(defineComponent({ render: () => h(PanelField, { field, onExpand }) }));
	app.provide(DocKey, docRef);
	app.provide(UpdateKey, update);
	app.provide(CommitKey, commit as any);
	app.provide(ResolveFieldKey, () => Control);
	app.provide(PanelContextKey, { onDetails: () => onDetails } as any);
	app.provide(FieldErrorsKey, ref(errors) as any);
	app.mount(root);
	mounted.push(app);
	return { root, update, commit, doc: docRef, onExpand };
}

const row = (root: HTMLElement, name: string) => root.querySelector<HTMLElement>(`[data-fieldname="${name}"]`)!;
const arrow = (root: HTMLElement) => root.querySelector(".lucide-arrow-up-right");

describe("a Text Editor row at rest", () => {
	const notes: FieldNode = { fieldname: "notes", fieldtype: "Text Editor", label: "Notes" };

	it("reads the text of the HTML over up to six lines, with no arrow", () => {
		const { root } = mount(notes, { notes: "<p>one</p><p>two <b>bold</b></p>" });
		const value = row(root, "notes").querySelector("span.line-clamp-6")!;

		expect(value.textContent).toBe("one\ntwo bold");
		expect(value.className).toContain("whitespace-pre-wrap");
		expect(arrow(root)).toBeNull();
	});

	it("shows the placeholder in the muted colour when empty", () => {
		const { root } = mount(notes, { notes: "" });
		const value = row(root, "notes").querySelector("span.line-clamp-6")!;

		expect(value.textContent).toBe("Add Notes...");
		expect(value.className).toContain("text-ink-gray-4");
	});

	it("opens its editor in panel mode on a click instead of Details", async () => {
		const { root, onExpand } = mount(notes, { notes: "<p>x</p>" });

		row(root, "notes").click();
		await nextTick();

		expect(root.querySelector("[data-control]")!.getAttribute("data-panel")).toBe("true");
		expect(onExpand).not.toHaveBeenCalled();
	});
});

describe("a Text Editor row", () => {
	const notes: FieldNode = { fieldname: "notes", fieldtype: "Text Editor", label: "Notes" };

	it("reads a value of only an image as Image, not as empty", () => {
		const { root } = mount(notes, { notes: '<p><img src="/files/a.png"></p>' });

		expect(row(root, "notes").querySelector("span.line-clamp-6")!.textContent).toBe("Image");
	});

	it("does not open when read-only", async () => {
		const { root, onExpand } = mount({ ...notes, readOnly: true }, { notes: "<p>x</p>" });

		row(root, "notes").click();
		await nextTick();

		expect(root.querySelector("[data-control]")).toBeNull();
		expect(onExpand).not.toHaveBeenCalled();
	});

	it("puts the opening value back on Esc and commits nothing", async () => {
		const { root, update, commit } = mount(notes, { notes: "<p>x</p>" });
		row(root, "notes").click();
		await nextTick();
		const control = root.querySelector<HTMLTextAreaElement>("[data-control]")!;
		control.value = "<p>y</p>";
		control.dispatchEvent(new Event("input"));

		control.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await nextTick();

		expect(update).toHaveBeenLastCalledWith("notes", "<p>x</p>");
		expect(commit.discard).toHaveBeenCalledWith("notes");
		expect(commit.commit).not.toHaveBeenCalled();
		expect(root.querySelector("[data-control]")).toBeNull();
	});
});

describe.each(["Text Editor", "Markdown Editor"])("a %s row with an error", (fieldtype) => {
	const field = { fieldname: "body", fieldtype, label: "Body" } as FieldNode;

	it("shows the message under the row and points the open control at it", async () => {
		const errors = { [fieldErrorKey("body")]: "Body is required" };
		const { root } = mount(field, { body: "" }, true, vi.fn(), errors);
		expect(root.textContent).toContain("Body is required");

		row(root, "body").click();
		await nextTick();

		const errorId = root.querySelector("[data-control]")!.getAttribute("data-error-id");
		expect(errorId).toBeTruthy();
		expect(document.getElementById(errorId!)!.textContent).toContain("Body is required");
	});
});

describe("a Markdown Editor row at rest", () => {
	const readme: FieldNode = { fieldname: "readme", fieldtype: "Markdown Editor", label: "Readme" };

	it("reads the raw markdown, keeping line breaks, with no arrow", () => {
		const { root } = mount(readme, { readme: "# Title\n\n- one" });
		const value = row(root, "readme").querySelector("span.line-clamp-6")!;

		expect(value.textContent).toBe("# Title\n\n- one");
		expect(arrow(root)).toBeNull();
	});

	it("opens its input in panel mode on a click instead of Details", async () => {
		const { root, onExpand } = mount(readme, { readme: "x" });

		row(root, "readme").click();
		await nextTick();

		expect(root.querySelector("[data-control]")!.getAttribute("data-panel")).toBe("true");
		expect(onExpand).not.toHaveBeenCalled();
	});
});

describe("a Geolocation row", () => {
	const place: FieldNode = { fieldname: "place", fieldtype: "Geolocation", label: "Place" };

	it("draws its own control at rest, with no arrow and no Add placeholder", () => {
		const { root } = mount(place, { place: "" });

		expect(root.querySelector("[data-control]")!.getAttribute("data-panel")).toBe("true");
		expect(arrow(root)).toBeNull();
		expect(root.textContent).not.toContain("Add Place");
	});

	it("does not open Details on a click", () => {
		const { root, onExpand } = mount(place, { place: "{}" });

		row(root, "place").click();

		expect(onExpand).not.toHaveBeenCalled();
	});
});

describe.each([
	["Code", "print(1)"],
	["JSON", "{}"],
	["HTML Editor", "<div></div>"],
	["Table", []],
])("a %s row", (fieldtype, value) => {
	const field = { fieldname: "heavy", fieldtype, label: "Heavy" } as FieldNode;

	it("keeps its summary and the ↗ to Details", () => {
		const { root } = mount(field, { heavy: value });

		expect(arrow(root)).not.toBeNull();
		expect(root.querySelector("[data-control]")).toBeNull();
	});

	it("opens Details on a click", () => {
		const { root, onExpand } = mount(field, { heavy: value });

		row(root, "heavy").click();

		expect(onExpand).toHaveBeenCalledWith(field);
	});
});
