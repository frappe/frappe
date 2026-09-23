// A reply's quote in the real editor: drawn under the body, sent once, gone on Discard, back after a failure.
// Emptying the body and the quote by hand is not a Discard.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type Component } from "vue";

const { runMethod } = vi.hoisted(() => ({ runMethod: vi.fn() }));
vi.mock("@framework/ui/api", async (importOriginal) => ({
	...((await importOriginal()) as object),
	runMethod,
}));

import { ComposerSurface } from "@/recordPage/composer";
import { closeComposer, composerDraft, setComposerWindow } from "@/shell/composer";
import ComposerWindow from "@/shell/ComposerWindow.vue";
import { RecordFeeds, RecordFeedsKey } from "../../feed/recordFeeds";
import { composerBuiltins, composerHost } from "../composerHost";
import { resetSenders } from "../emailSenders";
import RecordComposer from "../RecordComposer.vue";
import { RecordPageStub } from "./recordPageStub";

const USER = {
	name: "ann@example.com",
	full_name: "Ann",
	email: "ann@example.com",
	user_image: null,
	document_follow_notify: false,
};
const MAKE = "frappe.core.doctype.communication.email.make";
const EMAIL = {
	type: "email",
	name: "email:COMM-1",
	timestamp: "2026-09-20 10:00:00",
	data: {
		name: "COMM-1",
		subject: "Quote",
		sender: "bob@example.com",
		to: "ann@example.com, carl@example.com",
		cc: "dan@example.com",
		bcc: "",
		content: "<p>Hi</p>",
	},
};
const WROTE = "On September 20, 2026 10:00 AM, bob@example.com wrote:";

const apps: ReturnType<typeof createApp>[] = [];
let record = 0;

beforeEach(() => {
	vi.clearAllMocks();
	resetSenders();
	closeComposer();
	setComposerWindow("docked", { remember: true });
});
afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

function answers(make: () => Promise<unknown>) {
	runMethod.mockImplementation(async (method: string) => {
		if (method === MAKE) return make();
		return { data: { senders: [USER.email], default: null } };
	});
}

async function mountBand() {
	const docname = `LEAD-Q${++record}`;
	const page: any = {
		doctype: "Lead",
		docname,
		perms: { email: 1 },
		meta: {
			title_field: "lead_name",
			fields: [{ fieldname: "email_id", fieldtype: "Data", options: "Email" }],
		},
		doc: { lead_name: "Acme", email_id: "lead@example.com" },
		toast: { error: vi.fn(), success: vi.fn() },
		activity: { items: [EMAIL] },
	};
	page.composer = new ComposerSurface(
		composerHost("Lead", docname, { page: () => page, userEmail: USER.email })
	);
	page.composer.provideBuiltins(() => composerBuiltins(page.perms));
	const controller = { page, composer: page.composer, firePost: vi.fn(async () => {}) };
	const feeds = new RecordFeeds({
		docinfo: ref<any>({ attachments: [] }),
		controller: () => null,
		showTab: async () => true,
		reloadParts: async () => {},
		whileOnRecord: () => () => true,
	});
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () => [
			h(RecordPageStub, { controller }, () =>
				h(RecordComposer as Component, {
					controller,
					tabs: [{ name: "activity", label: "Activity" }],
					active: "activity",
					user: USER,
				})
			),
			h(ComposerWindow as Component, { user: USER }),
		],
	});
	app.provide(RecordFeedsKey, feeds);
	app.mount(root);
	apps.push(app);
	return { root, page };
}

// The editor loads by async import, which takes a while on a cold run.
async function reply(root: HTMLElement, page: any, replyAll = false) {
	page.composer.open("email", { draft: { replyTo: "email:COMM-1", replyAll } });
	await settle(() => root.querySelector(".ProseMirror"));
	await settle(() => root.querySelector("details > div")?.innerHTML);
}

async function settle(ready: () => unknown = () => true) {
	for (let i = 0; i < 100 && !ready(); i++)
		await new Promise((resolve) => setTimeout(resolve, 20));
	for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

function type(root: HTMLElement, text: string) {
	(root.querySelector(".ProseMirror") as any).editor.commands.insertContent(text);
}

function button(root: HTMLElement, label: string) {
	return [...root.querySelectorAll("button")].find((one) => one.textContent?.trim() === label)!;
}

// ProseMirror claims an Esc by its keyCode, which happy-dom leaves at 0 unless given.
function pressEscape(target: Element) {
	const init = { key: "Escape", keyCode: 27, bubbles: true, cancelable: true };
	target.dispatchEvent(new KeyboardEvent("keydown", init));
}

const inputs = (root: HTMLElement) =>
	[...root.querySelectorAll<HTMLInputElement>("input")].map((input) => input.value);
// happy-dom's DOMPurify drops the first tag's wrapper, so the markup is read as text.
const quoteText = (root: HTMLElement) => root.querySelector("details > div")?.textContent;
const sent = () =>
	runMethod.mock.calls.filter(([method]) => method === MAKE).map((call) => call[1]);
const count = (text: string, part: string) => text.split(part).length - 1;

describe("a reply's quote", () => {
	it("draws under the body on Reply all", async () => {
		const { root, page } = await mountBand();
		await reply(root, page, true);
		expect(quoteText(root)).toBe(`${WROTE}Hi`);
		expect(root.querySelector("[data-email-writer]")?.textContent).toContain("carl@example.com");
	});

	it("goes once, under the body", async () => {
		answers(async () => ({ data: { name: "COMM-5" } }));
		const { root, page } = await mountBand();
		await reply(root, page);
		type(root, "Thanks");
		await settle();
		button(root, "Send").click();
		await settle();
		expect(sent()).toHaveLength(1);
		const { content } = sent()[0];
		expect(content).toMatch(
			/^<p>Thanks<\/p><p class="reply-to-content"><\/p><blockquote>.*<\/blockquote>$/
		);
		expect([count(content, WROTE), count(content, "Hi"), count(content, "<blockquote>")]).toEqual([
			1, 1, 1,
		]);
	});

	it("comes back with the draft after a failed send, and a resend still quotes once", async () => {
		answers(async () => {
			throw new Error("Offline");
		});
		const { root, page } = await mountBand();
		await reply(root, page);
		type(root, "Thanks");
		await settle();
		button(root, "Send").click();
		await settle(() => root.querySelector("details > div")?.innerHTML);
		expect(composerDraft("Lead", page.docname, "email")).toMatchObject({
			content: "<p>Thanks</p>",
			quoted: expect.stringContaining(WROTE),
		});
		expect(quoteText(root)).toBe(`${WROTE}Hi`);
		button(root, "Send").click();
		await settle();
		expect(sent()).toHaveLength(2);
		expect(sent()[1].content).toBe(sent()[0].content);
		expect(count(sent()[1].content, WROTE)).toBe(1);
	});

	it.each([
		["Discard", (root: HTMLElement) => button(root, "Discard").click()],
		["Esc", (root: HTMLElement) => pressEscape(root.querySelector(".ProseMirror")!)],
	])(
		"goes on %s, which leaves the record's own prefill, as a fresh open does",
		async (_, discard) => {
			const { root, page } = await mountBand();
			await reply(root, page, true);
			expect(inputs(root)).toContain("Re: Quote");
			discard(root);
			await settle();
			expect(quoteText(root)).toBeUndefined();
			expect(inputs(root)).toContain("Re: Acme");
			const writer = root.querySelector("[data-email-writer]")!.textContent!;
			expect(writer).toContain("lead@example.com");
			expect(writer).not.toContain("carl@example.com");
			expect(composerDraft("Lead", page.docname, "email")).toBeUndefined();
		}
	);

	it("goes on select-all and Delete, which keep the reply's headers", async () => {
		const { root, page } = await mountBand();
		await reply(root, page, true);
		type(root, "Thanks");
		await settle();
		const quote = root.querySelector<HTMLElement>("details > div")!;
		quote.focus();
		const keys = { bubbles: true, cancelable: true };
		quote.dispatchEvent(new KeyboardEvent("keydown", { key: "a", ctrlKey: true, ...keys }));
		quote.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", ...keys }));
		await settle();
		expect(quoteText(root)).toBeUndefined();
		expect(inputs(root)).toContain("Re: Quote");
		expect(root.querySelector("[data-email-writer]")!.textContent).toContain("carl@example.com");
		expect(composerDraft("Lead", page.docname, "email")).toMatchObject({
			to: ["bob@example.com"],
			cc: expect.arrayContaining(["carl@example.com", "dan@example.com"]),
			subject: "Re: Quote",
			inReplyTo: "COMM-1",
			content: "",
			quoted: "",
		});
	});
});
