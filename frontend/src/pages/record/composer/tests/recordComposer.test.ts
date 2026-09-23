// The composer band: where it draws, the pill and its `+` menu, and the comment writer's send and draft.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type Component } from "vue";

const composerStub = vi.hoisted(() => ({
	addAttachment: null as any,
	focus: null as any,
	lastProps: null as any,
}));
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
		toast: { error: vi.fn(), success: vi.fn() },
		// Draws the menu open, one button per option, so a test reads and clicks it.
		Dropdown: vue.defineComponent({
			props: { options: Array },
			setup:
				(props: any, { slots }) =>
				() =>
					vue.h("div", [
						slots.default?.(),
						...props.options.map((option: any) =>
							vue.h(
								"button",
								{ "data-option": option.label, onClick: option.onClick },
								option.label
							)
						),
					]),
		}),
	};
});

vi.mock("@framework/ui/Composer", async () => {
	const vue = await import("vue");
	return {
		CommentComposer: vue.defineComponent({
			props: { modelValue: String, uploadFunction: Function },
			emits: ["update:modelValue", "submit", "remove-attachment"],
			setup(props, { slots, expose }) {
				composerStub.addAttachment = vi.fn();
				composerStub.focus = vi.fn();
				composerStub.lastProps = props;
				expose({ focus: composerStub.focus });
				return () =>
					vue.h("div", { "data-comment-composer": "" }, [
						slots.actions?.({
							addAttachment: composerStub.addAttachment,
							setUploading: () => {},
						}),
					]);
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

import { ComposerSurface } from "@/recordPage/composer";
import type { TabItem } from "@/recordPage/types";
import { closeComposer, composerDraft, openComposer, saveComposerDraft } from "@/shell/composer";
import { composerBuiltins, composerHost } from "../composerHost";
import RecordComposer from "../RecordComposer.vue";

const USER = {
	name: "ann@example.com",
	full_name: "Ann",
	email: "ann@example.com",
	user_image: null,
	document_follow_notify: false,
};
const ACTIVITY: TabItem = { name: "activity", label: "Activity" };
const EMAILS: TabItem = { name: "emails", label: "Emails" };
const DETAILS: TabItem = { name: "details", label: "Details" };
const run = vi.fn();
const FILES: TabItem = {
	name: "files",
	label: "Files",
	create: { label: "Attach a file", icon: "lucide-paperclip", run },
};
const CALLS: TabItem = {
	name: "calls",
	label: "Calls",
	composer: true,
	create: { label: "Log a call", icon: "lucide-phone", run },
};

const apps: ReturnType<typeof createApp>[] = [];
let record = 0;

beforeEach(() => {
	vi.clearAllMocks();
	closeComposer();
});
afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function fakeController() {
	const docname = `NOTE-${++record}`;
	const composer = new ComposerSurface(composerHost("Note", docname));
	composer.provideBuiltins(composerBuiltins);
	const page = {
		doctype: "Note",
		docname,
		composer,
		toast: { error: vi.fn(), success: vi.fn() },
	};
	return { page, composer, firePost: vi.fn(async () => {}) } as any;
}

async function mountBand(tabs: TabItem[], active: string, controller = fakeController()) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () => h(RecordComposer as Component, { controller, tabs, active, user: USER }),
	});
	app.mount(root);
	apps.push(app);
	await flush();
	return { root, controller };
}

async function flush() {
	for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

const band = (root: HTMLElement) => root.querySelector("[data-record-composer]");
const options = (root: HTMLElement) =>
	[...root.querySelectorAll("[data-option]")].map((one) => one.textContent);

describe("where the band draws", () => {
	it("draws on Activity, Emails and a tab that asks for it", async () => {
		const tabs = [ACTIVITY, EMAILS, CALLS, FILES, DETAILS];
		for (const active of ["activity", "emails", "calls"])
			expect(band((await mountBand(tabs, active)).root)).not.toBeNull();
	});

	it("draws nothing on Files or Details", async () => {
		const tabs = [ACTIVITY, FILES, DETAILS];
		for (const active of ["files", "details"])
			expect(band((await mountBand(tabs, active)).root)).toBeNull();
	});
});

describe("the pill", () => {
	it("lists every visible tab's create in strip order and runs the one picked", async () => {
		const { root, controller } = await mountBand([ACTIVITY, CALLS, FILES], "activity");
		expect(options(root)).toEqual(["Log a call", "Attach a file"]);
		(root.querySelector('[data-option="Attach a file"]') as HTMLElement).click();
		expect(run).toHaveBeenCalledWith(controller.page);
	});

	it("draws no `+` menu when no tab creates anything", async () => {
		const { root } = await mountBand([ACTIVITY, EMAILS], "activity");
		expect(root.querySelector("[data-composer-create]")).toBeNull();
		expect(root.querySelector("[data-composer-comment]")).not.toBeNull();
	});

	it("draws nothing with the comment writer hidden and nothing to create", async () => {
		const controller = fakeController();
		controller.composer.hide("comment");
		const { root } = await mountBand([ACTIVITY], "activity", controller);
		expect(band(root)).toBeNull();
	});

	it("opens the comment writer, docked, from the comment control", async () => {
		const { root, controller } = await mountBand([ACTIVITY], "activity");
		(root.querySelector("[data-composer-comment]") as HTMLElement).click();
		await flush();
		expect(controller.composer.active).toBe("comment");
		expect(root.querySelector("[data-composer-card]")).not.toBeNull();
		expect(root.querySelector("[data-comment-composer]")).not.toBeNull();
		expect(composerStub.focus).toHaveBeenCalled();
	});
});

describe("the docked card", () => {
	it("collapses back to the pill and keeps the draft", async () => {
		const controller = fakeController();
		openComposer("Note", controller.page.docname, "comment");
		saveComposerDraft("Note", controller.page.docname, "comment", {
			content: "<p>half</p>",
			attachments: [],
		});
		const { root } = await mountBand([ACTIVITY], "activity", controller);
		expect(composerStub.lastProps.modelValue).toBe("<p>half</p>");
		(root.querySelector("[data-composer-collapse]") as HTMLElement).click();
		await flush();
		expect(root.querySelector("[data-composer-card]")).toBeNull();
		expect(root.querySelector("[data-composer-pill]")).not.toBeNull();
		expect(composerDraft("Note", controller.page.docname, "comment")).toMatchObject({
			content: "<p>half</p>",
		});
	});

	it("hands a restored draft's attachments to the fresh editor", async () => {
		const controller = fakeController();
		const file = {
			name: "F-1",
			file_name: "a.pdf",
			file_url: "/private/files/a.pdf",
			file_type: "application/pdf",
		};
		openComposer("Note", controller.page.docname, "comment", {
			content: "",
			attachments: [file],
		});
		await mountBand([ACTIVITY], "activity", controller);
		expect(composerStub.addAttachment).toHaveBeenCalledWith(file);
	});

	it("draws a script's writer with its props, the page and close", async () => {
		const Poll = defineComponent({
			props: { question: String, page: Object, close: Function },
			setup: (props) => () =>
				h(
					"button",
					{ "data-poll": props.question, onClick: () => props.close?.() },
					props.page?.docname
				),
		});
		const controller = fakeController();
		controller.composer.add({
			name: "poll",
			label: "Poll",
			component: Poll,
			props: { question: "Lunch?" },
		});
		openComposer("Note", controller.page.docname, "poll");
		const { root } = await mountBand([ACTIVITY], "activity", controller);
		const poll = root.querySelector("[data-poll]") as HTMLElement;
		expect(poll.getAttribute("data-poll")).toBe("Lunch?");
		expect(poll.textContent).toBe(controller.page.docname);
		poll.click();
		await flush();
		expect(controller.composer.active).toBe("");
	});
});

describe("sending a comment", () => {
	it("adds the pending row, resolves it with the server's key and fires onPost", async () => {
		addComment.mockResolvedValue({
			data: {
				comments: [{ name: "C-7", creation: "2026-09-23 12:00:00" }],
				added: "C-7",
			},
		});
		const controller = fakeController();
		openComposer("Note", controller.page.docname, "comment");
		const { root } = await mountBand([ACTIVITY], "activity", controller);
		const editor = composerInstance(root);
		editor.$emit("submit", { body: "<p>Done</p>", attachments: [] });
		await flush();
		expect(addPendingActivity).toHaveBeenCalledWith(
			"Note",
			controller.page.docname,
			expect.objectContaining({ type: "comment" })
		);
		expect(pending.resolve).toHaveBeenCalledWith("comment:C-7", "2026-09-23 12:00:00");
		expect(controller.firePost).toHaveBeenCalledWith("comment:C-7");
		expect(root.querySelector("[data-composer-card]")).toBeNull();
	});

	it("drops the row and reopens with the draft when the post fails", async () => {
		addComment.mockRejectedValue(new Error("Not permitted"));
		const controller = fakeController();
		openComposer("Note", controller.page.docname, "comment");
		const { root } = await mountBand([ACTIVITY], "activity", controller);
		composerInstance(root).$emit("submit", {
			body: "<p>Done</p>",
			attachments: [],
		});
		await flush();
		expect(pending.drop).toHaveBeenCalled();
		expect(controller.page.toast.error).toHaveBeenCalledWith("Not permitted");
		expect(root.querySelector("[data-composer-card]")).not.toBeNull();
		expect(composerStub.lastProps.modelValue).toBe("<p>Done</p>");
	});
});

// The stub's own instance, reached through its element, so a test emits as the editor would.
function composerInstance(root: HTMLElement) {
	const element = root.querySelector("[data-comment-composer]") as any;
	return element.__vueParentComponent.proxy;
}
