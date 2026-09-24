// The shell's composer window: one writer moving between its record's band and the floating window,
// and what it does away from its record.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, reactive, ref, type Component } from "vue";

const composerStub = vi.hoisted(() => ({ mounts: 0, lastProps: null as any }));
const { addComment, pending, addPendingActivity } = vi.hoisted(() => {
	const pending = { resolve: vi.fn(), drop: vi.fn() };
	return {
		addComment: vi.fn(),
		pending,
		addPendingActivity: vi.fn((..._args: unknown[]) => pending),
	};
});

vi.mock("frappe-ui", async () => {
	const vue = await import("vue");
	const plain = (tag: string) =>
		vue.defineComponent({
			inheritAttrs: false,
			props: { label: String },
			setup:
				(props, { slots, attrs }) =>
				() =>
					vue.h(tag, attrs, slots.default?.() ?? props.label),
		});
	return {
		Avatar: plain("i"),
		Button: plain("button"),
		Tooltip: plain("span"),
		Dropdown: plain("div"),
		toast: { error: vi.fn(), success: vi.fn() },
	};
});

vi.mock("@framework/ui/Composer", async () => {
	const vue = await import("vue");
	return {
		CommentComposer: vue.defineComponent({
			props: { modelValue: String, uploadFunction: Function },
			emits: ["update:modelValue", "submit", "remove-attachment"],
			setup(props, { expose }) {
				composerStub.mounts++;
				composerStub.lastProps = props;
				expose({ focus: () => {} });
				return () => vue.h("div", { "data-comment-composer": "" });
			},
		}),
	};
});

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...((await importOriginal()) as object),
	addComment,
}));
vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => ({
	...((await importOriginal()) as object),
	addPendingActivity,
}));

import { toast } from "frappe-ui";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import type { Session } from "@framework/ui/api";
import { ComposerSurface } from "@/recordPage/composer";
import type { TabItem } from "@/recordPage/types";
import { composerBuiltins, composerHost } from "@/pages/record/composer/composerHost";
import RecordComposer from "@/pages/record/composer/RecordComposer.vue";
import { DEFAULT_DOCK_HEIGHT } from "@/pages/record/composer/useDockHeight";
import { RecordPageStub } from "@/pages/record/composer/tests/recordPageStub";
import { openWriterContext } from "@/pages/record/composer/writerContext";
import {
	closeComposer,
	composerDraft,
	composerRecord,
	openComposer,
	preferredWindow,
	saveComposerDraft,
	setComposerWindow,
} from "../composer";
import ComposerWindow from "../ComposerWindow.vue";

const USER = {
	name: "ann@example.com",
	full_name: "Ann",
	email: "ann@example.com",
	user_image: null,
	document_follow_notify: false,
};
const TABS: TabItem[] = [
	{ name: "activity", label: "Activity" },
	{ name: "files", label: "Files" },
];
const FLOAT_KEY = `desk:composer-float:${USER.name}`;

const apps: ReturnType<typeof createApp>[] = [];
let record = 0;

beforeEach(() => {
	vi.clearAllMocks();
	const session = { user: { name: USER.name }, roles: [], lang: "en", defaults: {} };
	setSession(session as unknown as Session);
	composerStub.mounts = 0;
	closeComposer();
	setComposerWindow("docked", { remember: true });
	localStorage.clear();
});
afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	resetSession();
});

function fakeController(title = "", perms: Record<string, number> = {}) {
	const docname = `NOTE-${++record}`;
	const composer = new ComposerSurface(composerHost("Note", docname), () => false);
	composer.provideBuiltins(composerBuiltins);
	const page = {
		doctype: "Note",
		docname,
		composer,
		perms,
		meta: { title_field: "title" },
		doc: reactive({ title }),
		toast: { error: vi.fn(), success: vi.fn() },
	};
	return { page, composer, firePost: vi.fn(async () => {}) } as any;
}

// Hiding the page is the reader leaving the record; hiding the band alone is a script hiding
// its column.
async function mountShell(controller = fakeController()) {
	const onRecord = ref(true);
	const band = ref(true);
	const active = ref("activity");
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () => [
			onRecord.value
				? h(RecordPageStub, { controller }, () =>
						band.value
							? h(RecordComposer as Component, {
									controller,
									tabs: TABS,
									active: active.value,
									user: USER,
							  })
							: null
				  )
				: null,
			h(ComposerWindow as Component, { user: USER }),
		],
	});
	app.mount(root);
	apps.push(app);
	await flush();
	return { root, controller, onRecord, band, active };
}

async function flush() {
	for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

async function click(selector: string) {
	(document.querySelector(selector) as HTMLElement).click();
	await flush();
}

const panel = () => document.querySelector<HTMLElement>("[data-composer-window]");
const editor = () => document.querySelector("[data-comment-composer]");
const inBand = (element: Element | null) => Boolean(element?.closest("[data-record-composer]"));
const title = () => document.querySelector("[data-composer-title]")?.textContent?.trim();

// The stub's own instance, reached through its element, so a test emits as the editor would.
function editorInstance() {
	return (editor() as any).__vueParentComponent.proxy;
}

describe("docking and floating", () => {
	it("moves the one writer between the band and the window without drawing it anew", async () => {
		const { controller } = await mountShell();
		controller.composer.open("comment");
		await flush();
		const drawn = editor();
		expect(inBand(panel())).toBe(true);
		expect(composerStub.mounts).toBe(1);

		await click("[data-composer-float]");
		expect(inBand(panel())).toBe(false);
		expect(panel()?.style.position).toBe("fixed");
		expect(editor()).toBe(drawn);
		expect(document.querySelector("[data-composer-pill]")).not.toBeNull();
		expect(preferredWindow()).toBe("floating");

		await click("[data-composer-dock-button]");
		expect(inBand(panel())).toBe(true);
		expect(editor()).toBe(drawn);
		expect(document.querySelector("[data-composer-pill]")).toBeNull();
		expect(composerStub.mounts).toBe(1);
		expect(preferredWindow()).toBe("docked");
	});

	it("keeps the floating window when the reader leaves the record, with no dock control", async () => {
		const { controller, onRecord } = await mountShell(fakeController("Quarterly plan"));
		controller.composer.open("comment", { window: "floating" });
		await flush();
		const drawn = editor();
		expect(document.querySelector("[data-composer-dock-button]")).not.toBeNull();

		onRecord.value = false;
		await flush();
		expect(editor()).toBe(drawn);
		expect(composerStub.mounts).toBe(1);
		expect(title()).toBe("Comment · Quarterly plan");
		expect(document.querySelector("[data-composer-dock-button]")).toBeNull();
	});

	it("draws nothing docked with no band, keeps the draft, and comes back with the band", async () => {
		const { controller, band, active } = await mountShell();
		const { docname } = controller.page;
		openComposer("Note", docname, "comment");
		saveComposerDraft("Note", docname, "comment", { content: "<p>half</p>", attachments: [] });
		await flush();
		expect(panel()).not.toBeNull();

		active.value = "files";
		await flush();
		expect(panel()).toBeNull();
		band.value = false;
		await flush();
		expect(panel()).toBeNull();
		expect(composerDraft("Note", docname, "comment")).toMatchObject({ content: "<p>half</p>" });

		band.value = true;
		active.value = "activity";
		await flush();
		expect(inBand(panel())).toBe(true);
		expect(composerStub.lastProps.modelValue).toBe("<p>half</p>");
	});

	it("floats an open that asks to, over the window's stored place, and remembers nothing", async () => {
		const rect = { x: 10, y: 20, width: 500, height: 400 };
		localStorage.setItem(FLOAT_KEY, JSON.stringify({ mode: "docked", rect }));
		const { controller } = await mountShell();
		controller.composer.open("comment", { window: "floating" });
		await flush();
		expect(inBand(panel())).toBe(false);
		expect(panel()?.style.left).toBe("10px");
		expect(preferredWindow()).toBe("docked");
		expect(controller.composer.window).toBe("floating");
	});
});

describe("where the floating card mounts", () => {
	it("pulls a stored rectangle back on screen before it mounts", async () => {
		const rect = { x: innerWidth + 400, y: innerHeight + 300, width: 500, height: 400 };
		localStorage.setItem(FLOAT_KEY, JSON.stringify({ mode: "floating", rect }));
		const { controller } = await mountShell();
		controller.composer.open("comment", { window: "floating" });
		await flush();
		expect(panel()?.style.left).toBe(`${innerWidth - 500}px`);
		expect(panel()?.style.top).toBe(`${innerHeight - 400}px`);
	});

	it("shrinks a stored rectangle wider or taller than the screen to fit it", async () => {
		const rect = { x: -40, y: 10, width: innerWidth + 200, height: innerHeight + 100 };
		localStorage.setItem(FLOAT_KEY, JSON.stringify({ mode: "floating", rect }));
		const { controller } = await mountShell();
		controller.composer.open("comment", { window: "floating" });
		await flush();
		expect(panel()?.style.left).toBe("0px");
		expect(panel()?.style.top).toBe("0px");
		expect(panel()?.style.width).toBe(`${innerWidth}px`);
		expect(panel()?.style.height).toBe(`${innerHeight}px`);
	});
});

describe("the docked height", () => {
	it("sizes the card from the dock height while docked, and not while floating", async () => {
		const rect = { x: 10, y: 20, width: 500, height: 400 };
		localStorage.setItem(FLOAT_KEY, JSON.stringify({ mode: "docked", rect }));
		const { controller } = await mountShell();
		controller.composer.open("comment");
		await flush();
		expect(panel()?.style.height).toBe(`${DEFAULT_DOCK_HEIGHT}px`);
		expect(document.querySelector("[data-composer-handle]")).not.toBeNull();

		await click("[data-composer-float]");
		expect(panel()?.style.height).toBe("400px");
		expect(document.querySelector("[data-composer-handle]")).toBeNull();
	});

	it("starts a drag from the card's drawn height", async () => {
		const { controller } = await mountShell();
		controller.composer.open("comment");
		await flush();
		Object.defineProperty(panel(), "offsetHeight", { configurable: true, value: 250 });
		const handle = document.querySelector<HTMLElement>("[data-composer-handle]")!;
		const pointer = (type: string, clientY: number) =>
			handle.dispatchEvent(new PointerEvent(type, { clientY, pointerId: 1, bubbles: true }));

		pointer("pointerdown", 500);
		pointer("pointermove", 400);
		pointer("pointerup", 400);
		await flush();
		expect(panel()?.style.height).toBe("350px");
	});
});

describe("a script hiding the band", () => {
	it("leaves the writer its live record: onPost, no dock control, the live title", async () => {
		addComment.mockResolvedValue({ data: { comments: [], added: "C-9" } });
		const { controller, band } = await mountShell(fakeController("Quarterly plan"));
		controller.composer.open("comment", { window: "floating" });
		await flush();

		band.value = false;
		await flush();
		expect(composerRecord()?.page).toBe(controller.page);
		expect(document.querySelector("[data-composer-dock-button]")).toBeNull();
		controller.page.doc.title = "Yearly plan";
		await flush();
		expect(title()).toBe("Comment · Yearly plan");

		editorInstance().$emit("submit", { body: "<p>Done</p>", attachments: [] });
		await flush();
		expect(controller.firePost).toHaveBeenCalledWith("comment:C-9");
	});
});

describe("the title", () => {
	it("follows the record's title while its page is open", async () => {
		const { controller } = await mountShell(fakeController("Quarterly plan"));
		controller.composer.open("comment");
		await flush();
		controller.page.doc.title = "Yearly plan";
		await flush();
		expect(title()).toBe("Comment · Yearly plan");
	});
});

describe("one window at a time", () => {
	it("gives the window to a second record's open, retitled, and keeps the first draft", async () => {
		const { controller } = await mountShell(fakeController("Quarterly plan"));
		const { docname } = controller.page;
		controller.composer.open("comment", { window: "floating" });
		await flush();
		editorInstance().$emit("update:modelValue", "<p>first</p>");
		await flush();

		openComposer("Note", "NOTE-OTHER", "comment", undefined, "floating");
		await flush();
		expect(title()).toBe("Comment · NOTE-OTHER");
		expect(composerStub.lastProps.modelValue).not.toContain("first");
		expect(composerDraft("Note", docname, "comment")).toMatchObject({ content: "<p>first</p>" });
	});
});

describe("away from the record", () => {
	async function floatedAway(controller = fakeController()) {
		const shell = await mountShell(controller);
		shell.controller.composer.open("comment", { window: "floating" });
		await flush();
		shell.onRecord.value = false;
		await flush();
		return shell;
	}

	it("says a failed post through the shell's toast and reopens with the draft", async () => {
		addComment.mockRejectedValue(new Error("Not permitted"));
		const { controller } = await floatedAway();
		editorInstance().$emit("submit", { body: "<p>Done</p>", attachments: [] });
		await flush();
		expect(toast.error).toHaveBeenCalledWith("Not permitted");
		expect(controller.page.toast.error).not.toHaveBeenCalled();
		expect(composerStub.lastProps.modelValue).toBe("<p>Done</p>");
	});

	it("reopens a failed post titled after its record, with the record's rights kept", async () => {
		addComment.mockRejectedValue(new Error("Offline"));
		await floatedAway(fakeController("Quarterly plan", { write: 1 }));
		editorInstance().$emit("submit", { body: "<p>Done</p>", attachments: [] });
		await flush();
		expect(inBand(panel())).toBe(false);
		expect(title()).toBe("Comment · Quarterly plan");
		expect(openWriterContext().perms).toEqual({ write: 1 });
	});

	it("keeps a script's label on a built-in writer", async () => {
		const controller = fakeController("Quarterly plan");
		controller.composer.update("comment", { label: "Note" });
		await floatedAway(controller);
		expect(title()).toBe("Note · Quarterly plan");
	});

	it("fires no onPost for a post that goes", async () => {
		addComment.mockResolvedValue({ data: { comments: [], added: "C-9" } });
		const { controller } = await floatedAway();
		editorInstance().$emit("submit", { body: "<p>Done</p>", attachments: [] });
		await flush();
		expect(pending.resolve).toHaveBeenCalledWith("comment:C-9", undefined);
		expect(controller.firePost).not.toHaveBeenCalled();
		expect(panel()).toBeNull();
	});

	it("holds a script's writer until its record is back", async () => {
		const Poll = defineComponent({
			props: { page: Object },
			setup: (props) => () => h("div", { "data-poll": "" }, props.page?.docname),
		});
		const controller = fakeController();
		controller.composer.add({ name: "poll", label: "Poll", component: Poll });
		const { onRecord } = await mountShell(controller);
		controller.composer.open("poll", { window: "floating" });
		await flush();
		expect(document.querySelector("[data-poll]")?.textContent).toBe(controller.page.docname);

		onRecord.value = false;
		await flush();
		expect(panel()).toBeNull();

		onRecord.value = true;
		await flush();
		expect(document.querySelector("[data-poll]")).not.toBeNull();
	});
});
