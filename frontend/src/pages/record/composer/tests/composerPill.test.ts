// The collapsed pill's Reply: drawn only while the `email` writer is handed in, and it opens that writer.
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
const COMMENT = { name: "comment", label: "Comment" };
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
				...props,
				onOpen: (name: string) => opened.push(name),
			}),
	});
	app.mount(root);
	apps.push(app);
	await nextTick();
	return { root, opened };
}

const replyButton = (root: HTMLElement) => root.querySelector<HTMLElement>("[data-composer-reply]");

describe("the pill's Reply", () => {
	it("is absent without the email writer", async () => {
		const { root } = await mountPill({ comment: COMMENT });
		expect(replyButton(root)).toBeNull();
		expect(root.querySelector("[data-composer-comment]")).not.toBeNull();
	});

	it("opens the email writer, named Reply", async () => {
		const { root, opened } = await mountPill({ comment: COMMENT, email: EMAIL });
		const reply = replyButton(root)!;
		expect(reply.textContent).toBe("Reply");
		reply.click();
		expect(opened).toEqual(["email"]);
	});

	it("takes the free space when the comment control is hidden", async () => {
		const { root } = await mountPill({ email: EMAIL });
		expect(replyButton(root)!.classList.contains("ml-auto")).toBe(true);
	});
});
