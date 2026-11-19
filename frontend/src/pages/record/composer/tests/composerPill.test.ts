// The collapsed pill: Reply leads while the `email` writer is handed in, else the comment control.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type Component } from "vue";

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
	return { Avatar: plain("i"), Button: plain("button"), Tooltip: plain("span"), Dropdown: plain("div") };
});

import ComposerPill from "../ComposerPill.vue";

const USER = { name: "ann@example.com", full_name: "Ann" };
const COMMENT = { name: "comment", label: "Comment", icon: "lucide-message-square" };
const EMAIL = { name: "email", label: "Email" };

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mountPill(props: Record<string, unknown>) {
	const opened: string[] = [];
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () =>
			h(ComposerPill as Component, {
				creates: [],
				user: USER,
				title: "Acme",
				...props,
				onOpen: (name: string) => opened.push(name),
			}),
	});
	app.mount(root);
	apps.push(app);
	await nextTick();
	return { root, opened };
}

const replyControl = (root: HTMLElement) =>
	root.querySelector<HTMLElement>("[data-composer-reply]");
const commentControl = (root: HTMLElement) =>
	root.querySelector<HTMLElement>("[data-composer-comment]");

describe("the pill", () => {
	it("leads with Reply to the record and keeps Comment as an icon button", async () => {
		const { root, opened } = await mountPill({ comment: COMMENT, email: EMAIL });
		const reply = replyControl(root)!;
		expect(reply.tagName).toBe("BUTTON");
		expect(reply.textContent).toContain("Reply to Acme");
		expect(reply.querySelector("i")).not.toBeNull();
		const comment = commentControl(root)!;
		expect(comment.getAttribute("icon")).toBe("lucide-message-square");
		expect(comment.getAttribute("tooltip")).toBe("Add a comment");
		expect(comment.textContent).toBe("Add a comment");
		reply.click();
		comment.click();
		expect(opened).toEqual(["email", "comment"]);
	});

	it("leads with the comment control without the email writer", async () => {
		const { root, opened } = await mountPill({ comment: COMMENT });
		expect(replyControl(root)).toBeNull();
		const comment = commentControl(root)!;
		expect(comment.textContent).toContain("Add a comment…");
		expect(comment.querySelector("i")).not.toBeNull();
		comment.click();
		expect(opened).toEqual(["comment"]);
	});

	it("draws no Comment button when the comment writer is hidden", async () => {
		const { root, opened } = await mountPill({ email: EMAIL });
		expect(commentControl(root)).toBeNull();
		replyControl(root)!.click();
		expect(opened).toEqual(["email"]);
	});

	it("sizes the Comment and `+` buttons alike, and pushes `+` right when alone", async () => {
		const creates = [{ label: "Log a call", onClick: () => {} }];
		const full = (await mountPill({ comment: COMMENT, email: EMAIL, creates })).root;
		const plus = full.querySelector("[data-composer-create] button")!;
		expect(plus.getAttribute("size")).toBe(commentControl(full)!.getAttribute("size"));
		const pushed = (root: HTMLElement) =>
			root.querySelector("[data-composer-create]")!.classList.contains("ml-auto");
		expect(pushed(full)).toBe(false);
		expect(pushed((await mountPill({ creates })).root)).toBe(true);
	});
});
