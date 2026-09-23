// The email writer in the band: its sender rows, the notice with no sender, the send, the uploads
// and the pill's Reply.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type Component } from "vue";

const composerStub = vi.hoisted(() => ({ lastProps: null as any }));
const { runMethod, attachFile, defaultTransport, pending, addPendingActivity } = vi.hoisted(() => {
	const pending = { resolve: vi.fn(), drop: vi.fn() };
	return {
		runMethod: vi.fn(),
		attachFile: vi.fn(),
		defaultTransport: vi.fn(),
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
		EmailComposer: vue.defineComponent({
			props: {
				modelValue: String,
				from: String,
				to: Array,
				cc: Array,
				bcc: Array,
				subject: String,
				showFrom: Boolean,
				showSubject: Boolean,
				senders: Array,
				submitting: Boolean,
				fill: Boolean,
				disabled: Boolean,
				searchRecipients: Function,
				uploadFunction: Function,
			},
			emits: [
				"update:modelValue",
				"update:from",
				"update:to",
				"update:subject",
				"submit",
				"remove-attachment",
				"discard",
			],
			setup(props, { slots, expose }) {
				composerStub.lastProps = props;
				expose({ focus: () => {} });
				return () =>
					vue.h("div", { "data-email-composer": "" }, [
						slots.actions?.({ addAttachment: () => {}, setUploading: () => {} }),
						slots.footer?.(),
					]);
			},
		}),
	};
});

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...((await importOriginal()) as object),
	runMethod,
	attachFile,
}));
vi.mock("@framework/ui/FileUpload", async (importOriginal) => ({
	...((await importOriginal()) as object),
	defaultTransport,
}));
vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => ({
	...((await importOriginal()) as object),
	addPendingActivity,
}));

import { ComposerSurface } from "@/recordPage/composer";
import type { TabItem } from "@/recordPage/types";
import {
	activeWriter,
	closeComposer,
	composerDraft,
	openComposer,
	rememberWindow,
	saveComposerDraft,
} from "@/shell/composer";
import ComposerWindow from "@/shell/ComposerWindow.vue";
import { RecordFeeds, RecordFeedsKey } from "../../feed/recordFeeds";
import { composerBuiltins, composerHost } from "../composerHost";
import { asEmailDraft } from "../emailDraft";
import { resetSenders } from "../emailSenders";
import RecordComposer from "../RecordComposer.vue";

const USER = {
	name: "ann@example.com",
	full_name: "Ann",
	email: "ann@example.com",
	user_image: null,
	document_follow_notify: false,
};
const ACTIVITY: TabItem = { name: "activity", label: "Activity" };
const MAKE = "frappe.core.doctype.communication.email.make";
const SENDERS = "frappe.email.inbox.get_outgoing_senders";

const apps: ReturnType<typeof createApp>[] = [];
let record = 0;

beforeEach(() => {
	vi.clearAllMocks();
	resetSenders();
	closeComposer();
	rememberWindow("docked");
});
afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function answers(
	senders: { senders: string[]; default: string | null },
	make = async () => ({ data: { name: "COMM-5" } })
) {
	runMethod.mockImplementation(async (method: string) => {
		if (method === SENDERS) return { data: senders };
		if (method === MAKE) return make();
		throw new Error(`unexpected ${method}`);
	});
}

// The senders answer waits for `release`, as a slow lookup does.
function heldSenders(senders: { senders: string[]; default: string | null }) {
	let release = () => {};
	const held = new Promise<void>((resolve) => (release = resolve));
	runMethod.mockImplementation(async (method: string) => {
		if (method === SENDERS) return held.then(() => ({ data: senders }));
		if (method === MAKE) return { data: { name: "COMM-5" } };
		throw new Error(`unexpected ${method}`);
	});
	return () => release();
}

function fakeController(perms: Record<string, number> = { email: 1 }) {
	const docname = `LEAD-${++record}`;
	const composer = new ComposerSurface(composerHost("Lead", docname));
	composer.provideBuiltins(() => composerBuiltins(perms));
	const page = {
		doctype: "Lead",
		docname,
		composer,
		perms,
		meta: {
			title_field: "lead_name",
			fields: [{ fieldname: "email_id", fieldtype: "Data", options: "Email" }],
		},
		doc: { lead_name: "Acme", email_id: "lead@example.com" },
		toast: { error: vi.fn(), success: vi.fn() },
	};
	return { page, composer, firePost: vi.fn(async () => {}) } as any;
}

// The editor empties its body before it says Discard.
function discard(root: HTMLElement) {
	editor(root).$emit("update:modelValue", "");
	editor(root).$emit("discard");
}

async function mountEmail(
	controller = fakeController(),
	draft = asEmailDraft({}),
	feeds = recordFeeds().feeds
) {
	saveComposerDraft("Lead", controller.page.docname, "email", draft);
	openComposer("Lead", controller.page.docname, "email");
	return mountBand(controller, feeds);
}

async function mountBand(controller: any, feeds = recordFeeds().feeds) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () => [
			h(RecordComposer as Component, { controller, tabs: [ACTIVITY], active: "activity", user: USER }),
			h(ComposerWindow as Component, { user: USER }),
		],
	});
	app.provide(RecordFeedsKey, feeds);
	app.mount(root);
	apps.push(app);
	await flush();
	return { root, controller };
}

function recordFeeds() {
	const docinfo = ref<any>({ attachments: [] });
	const feeds = new RecordFeeds({
		docinfo,
		controller: () => null,
		showTab: async () => true,
		reloadParts: async () => {},
		whileOnRecord: () => () => true,
	});
	return { feeds, docinfo };
}

async function flush() {
	for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

function editor(root: HTMLElement) {
	const element = root.querySelector("[data-email-composer]") as any;
	return element.__vueParentComponent.proxy;
}

describe("the sender", () => {
	it("draws a From row with two senders, the user's own address picked", async () => {
		answers({ senders: ["sales@example.com", USER.email], default: null });
		await mountEmail();
		expect(composerStub.lastProps.showFrom).toBe(true);
		expect(composerStub.lastProps.from).toBe(USER.email);
		expect(composerStub.lastProps.showSubject).toBe(true);
		expect(composerStub.lastProps.disabled).toBe(false);
	});

	it("draws no From row with one sender, and sends as it", async () => {
		answers({ senders: ["sales@example.com"], default: null });
		const { root } = await mountEmail();
		expect(composerStub.lastProps.showFrom).toBe(false);
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		await flush();
		expect(runMethod.mock.calls.find(([method]) => method === MAKE)?.[1].sender).toBe(
			"sales@example.com"
		);
	});

	it("draws no From row and no notice with only a default account", async () => {
		answers({ senders: [], default: "notify@example.com" });
		const { root } = await mountEmail();
		expect(composerStub.lastProps.showFrom).toBe(false);
		expect(root.querySelector("[data-email-no-sender]")).toBeNull();
		expect(composerStub.lastProps.disabled).toBe(false);
	});

	it("says there is no outgoing account and disables the send with none at all", async () => {
		answers({ senders: [], default: null });
		const { root } = await mountEmail();
		expect(root.querySelector("[data-email-no-sender]")?.textContent).toContain(
			"No outgoing email account"
		);
		expect(composerStub.lastProps.disabled).toBe(true);
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		await flush();
		expect(runMethod.mock.calls.some(([method]) => method === MAKE)).toBe(false);
	});

	it("asks for the senders once, when the writer first opens, not with the pill", async () => {
		answers({ senders: [USER.email], default: null });
		const controller = fakeController();
		const { root } = await mountBand(controller);
		const asked = () => runMethod.mock.calls.filter(([method]) => method === SENDERS).length;
		expect(root.querySelector("[data-composer-pill]")).not.toBeNull();
		expect(asked()).toBe(0);
		controller.composer.open("email");
		await flush();
		expect(root.querySelector("[data-email-writer]")).not.toBeNull();
		expect(asked()).toBe(1);
		controller.composer.close();
		await flush();
		controller.composer.open("email");
		await flush();
		expect(asked()).toBe(1);
	});
});

describe("sending an email", () => {
	it("posts the draft's headers with the editor's body, once, and fires onPost", async () => {
		answers({ senders: [USER.email], default: null });
		const draft = asEmailDraft({ to: "bob@example.com", subject: "Re: Acme", inReplyTo: "COMM-1" });
		const { root, controller } = await mountEmail(undefined, draft);
		expect(composerStub.lastProps.to).toEqual([{ email: "bob@example.com" }]);
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		await flush();
		const makes = runMethod.mock.calls.filter(([method]) => method === MAKE);
		expect(makes).toHaveLength(1);
		expect(makes[0][1]).toMatchObject({
			recipients: "bob@example.com",
			subject: "Re: Acme",
			content: "<p>Hi</p>",
			in_reply_to: "COMM-1",
		});
		expect(pending.resolve).toHaveBeenCalledWith("email:COMM-5");
		expect(controller.firePost).toHaveBeenCalledWith("email:COMM-5");
		expect(root.querySelector("[data-composer-card]")).toBeNull();
	});

	it("sends once, as the looked-up sender, when both submits came before the lookup", async () => {
		const release = heldSenders({ senders: ["sales@example.com"], default: null });
		const { root } = await mountEmail(undefined, asEmailDraft({ to: "bob@example.com" }));
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		await flush();
		expect(composerStub.lastProps.submitting).toBe(true);
		expect(runMethod.mock.calls.some(([method]) => method === MAKE)).toBe(false);
		release();
		await flush();
		const makes = runMethod.mock.calls.filter(([method]) => method === MAKE);
		expect(makes).toHaveLength(1);
		expect(makes[0][1].sender).toBe("sales@example.com");
	});

	it("leaves open a writer the reader opened on another record while the send waited", async () => {
		const release = heldSenders({ senders: [USER.email], default: null });
		const { root } = await mountEmail(undefined, asEmailDraft({ to: "bob@example.com" }));
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		openComposer("Lead", "LEAD-ELSEWHERE", "email");
		release();
		await flush();
		expect(runMethod.mock.calls.filter(([method]) => method === MAKE)).toHaveLength(1);
		expect(activeWriter("Lead", "LEAD-ELSEWHERE")).toBe("email");
	});

	it("Discard leaves what a fresh open shows, the chosen sender kept", async () => {
		answers({ senders: ["sales@example.com", USER.email], default: null });
		const draft = asEmailDraft({
			from: "sales@example.com",
			to: "bob@example.com",
			cc: "carl@example.com",
			bcc: "eve@example.com",
			subject: "Re: Quote",
			content: "<p>Hi</p>",
			inReplyTo: "COMM-1",
		});
		const { root, controller } = await mountEmail(undefined, draft);
		discard(root);
		await flush();
		expect(composerStub.lastProps).toMatchObject({
			from: "sales@example.com",
			to: [{ email: "lead@example.com" }],
			cc: [],
			bcc: [],
			subject: "Re: Acme",
		});
		expect(composerDraft("Lead", controller.page.docname, "email")).toBeUndefined();
	});

	it("keeps the headers and the reply's thread when the body is emptied", async () => {
		answers({ senders: [USER.email], default: null });
		const draft = asEmailDraft({
			to: "bob@example.com",
			cc: "carl@example.com",
			subject: "Re: Quote",
			content: "<p>Hi</p>",
			inReplyTo: "COMM-1",
		});
		const { root, controller } = await mountEmail(undefined, draft);
		editor(root).$emit("update:modelValue", "");
		await flush();
		expect(composerStub.lastProps).toMatchObject({
			to: [{ email: "bob@example.com" }],
			cc: [{ email: "carl@example.com" }],
			subject: "Re: Quote",
		});
		expect(composerDraft("Lead", controller.page.docname, "email")).toMatchObject({
			inReplyTo: "COMM-1",
			content: "",
		});
	});

	it("sends what was written when Discard came while the send waited on the lookup", async () => {
		const release = heldSenders({ senders: ["sales@example.com"], default: null });
		const draft = asEmailDraft({ to: "bob@example.com", subject: "Re: Quote", inReplyTo: "COMM-1" });
		const { root } = await mountEmail(undefined, draft);
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		discard(root);
		release();
		await flush();
		const makes = runMethod.mock.calls.filter(([method]) => method === MAKE);
		expect(makes).toHaveLength(1);
		expect(makes[0][1]).toMatchObject({
			recipients: "bob@example.com",
			subject: "Re: Quote",
			in_reply_to: "COMM-1",
			sender: "sales@example.com",
			content: "<p>Hi</p>",
		});
	});

	it("takes a script's draft on the next open after a Discard", async () => {
		answers({ senders: [USER.email], default: null });
		const draft = asEmailDraft({ to: "bob@example.com", content: "<p>Hi</p>" });
		const { root, controller } = await mountEmail(undefined, draft);
		discard(root);
		await flush();
		controller.composer.close();
		await flush();
		controller.composer.open("email", { draft: { subject: "From a script" } });
		await flush();
		expect(composerStub.lastProps.subject).toBe("From a script");
	});

	it("keeps a written draft over a script's on the next open", async () => {
		answers({ senders: [USER.email], default: null });
		const { root, controller } = await mountEmail();
		editor(root).$emit("update:subject", "Mine");
		await flush();
		controller.composer.close();
		await flush();
		controller.composer.open("email", { draft: { subject: "From a script" } });
		await flush();
		expect(composerStub.lastProps.subject).toBe("Mine");
	});

	it("saves what the reader types into the record's draft", async () => {
		answers({ senders: [USER.email], default: null });
		const { root, controller } = await mountEmail();
		editor(root).$emit("update:to", [{ email: "carl@example.com", label: "Carl" }]);
		editor(root).$emit("update:subject", "Hello");
		await flush();
		expect(composerDraft("Lead", controller.page.docname, "email")).toMatchObject({
			to: ["carl@example.com"],
			subject: "Hello",
		});
	});

	it("reopens with the draft and a toast when the send fails", async () => {
		answers({ senders: [USER.email], default: null }, async () => {
			throw new Error("Rejected");
		});
		const { root, controller } = await mountEmail(undefined, asEmailDraft({ subject: "Kept" }));
		editor(root).$emit("update:modelValue", "<p>Hi</p>");
		editor(root).$emit("submit", { body: "<p>Hi</p>", attachments: [] });
		await flush();
		expect(pending.drop).toHaveBeenCalled();
		expect(controller.page.toast.error).toHaveBeenCalledWith("Rejected");
		expect(composerStub.lastProps.subject).toBe("Kept");
		expect(composerStub.lastProps.modelValue).toBe("<p>Hi</p>");
	});
});

describe("the pill", () => {
	it("shows Reply only with the email right", async () => {
		const reply = async (perms: Record<string, number>) => {
			const { root } = await mountBand(fakeController(perms));
			expect(root.querySelector("[data-composer-pill]")).not.toBeNull();
			return root.querySelector("[data-composer-reply]");
		};
		expect(await reply({ email: 1 })).not.toBeNull();
		expect(await reply({ email: 0 })).toBeNull();
	});

	it("names Reply after the record's title field", async () => {
		const { root } = await mountBand(fakeController());
		const reply = root.querySelector("[data-composer-reply]")!;
		expect(reply.textContent).toContain("Reply to Acme");
	});
});

describe("uploads", () => {
	const FILE = new File(["x"], "brief.pdf", { type: "application/pdf" });
	const ROW = {
		name: "FILE-1",
		file_name: "brief.pdf",
		file_url: "/private/files/brief.pdf",
		is_private: 1,
		creation: "2026-09-23 10:00:00",
		owner: USER.name,
	};

	function inline() {
		return { signal: new AbortController().signal, onProgress: vi.fn() };
	}

	it("hang on the record with the write right, and the Files tab gains the row", async () => {
		answers({ senders: [USER.email], default: null });
		attachFile.mockImplementation(async (...call: any[]) => {
			call[4].onProgress(5, 10);
			return { data: { attachments: [ROW], file: ROW.name } };
		});
		const { feeds, docinfo } = recordFeeds();
		const controller = fakeController({ email: 1, write: 1 });
		await mountEmail(controller, undefined, feeds);
		const options = inline();

		const media = await composerStub.lastProps.uploadFunction(FILE, options);

		const [doctype, docname, file, fields, sent] = attachFile.mock.calls[0];
		expect([doctype, docname, file]).toEqual(["Lead", controller.page.docname, FILE]);
		expect(fields.is_private).toBe(1);
		expect(sent.signal).toBe(options.signal);
		expect(options.onProgress).toHaveBeenCalledWith({ loaded: 5, total: 10, percent: 50 });
		expect(media).toMatchObject({ name: ROW.name, file_url: ROW.file_url, is_private: 1 });
		expect(defaultTransport).not.toHaveBeenCalled();
		expect(docinfo.value.attachments).toEqual([ROW]);
	});

	it("keep an attached file in the draft", async () => {
		answers({ senders: [USER.email], default: null });
		attachFile.mockResolvedValue({ data: { attachments: [ROW], file: ROW.name } });
		const controller = fakeController({ email: 1, write: 1 });
		await mountEmail(controller);
		await composerStub.lastProps.uploadFunction(FILE);
		await flush();
		expect(composerDraft("Lead", controller.page.docname, "email")?.attachments).toEqual([
			expect.objectContaining({ name: ROW.name, file_url: ROW.file_url }),
		]);
	});

	it("hang on nothing without the write right, and the Files tab is left alone", async () => {
		answers({ senders: [USER.email], default: null });
		defaultTransport.mockResolvedValue({ name: "FILE-2", file_url: "/private/files/brief.pdf" });
		const { feeds, docinfo } = recordFeeds();
		await mountEmail(fakeController({ email: 1, write: 0 }), undefined, feeds);
		const options = inline();

		const media = await composerStub.lastProps.uploadFunction(FILE, options);

		expect(attachFile).not.toHaveBeenCalled();
		const [file, args, sent] = defaultTransport.mock.calls[0];
		expect(file).toBe(FILE);
		expect(args).toEqual({ isPrivate: true });
		expect(sent.signal).toBe(options.signal);
		expect(media).toMatchObject({ name: "FILE-2", is_private: 1 });
		expect(docinfo.value.attachments).toEqual([]);
	});
});
