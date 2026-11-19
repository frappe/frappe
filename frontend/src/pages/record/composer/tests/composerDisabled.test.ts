// The composers' `disabled` prop on the real components: a read-only body, attach and send off,
// and a submit that goes nowhere.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type Component } from "vue";
import { CommentComposer, EmailComposer } from "@framework/ui/Composer";

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount(component: Component, disabled = ref(true)) {
	const composer = ref<{ submit: () => void } | null>(null);
	const onSubmit = vi.fn();
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({
		render: () =>
			h(component, {
				ref: composer,
				modelValue: "<p>Hi</p>",
				submitLabel: "Send",
				uploadFunction: async () => ({}),
				disabled: disabled.value,
				onSubmit,
			}),
	});
	app.mount(root);
	apps.push(app);
	await settle();
	return { root, composer, onSubmit, disabled };
}

async function settle() {
	for (let i = 0; i < 3; i++) await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

function sendButton(root: HTMLElement) {
	return [...root.querySelectorAll("button")].find((one) => one.textContent?.includes("Send"))!;
}

const attachButton = (root: HTMLElement) =>
	root.querySelector("button[aria-label='Attach file']") as HTMLButtonElement;
const body = (root: HTMLElement) => root.querySelector(".ProseMirror") as HTMLElement;

describe("a disabled composer", () => {
	it("keeps the email body read-only, attach and send off, and refuses a submit", async () => {
		const { root, composer, onSubmit } = await mount(EmailComposer);
		expect(body(root).getAttribute("contenteditable")).toBe("false");
		expect(attachButton(root).disabled).toBe(true);
		expect(sendButton(root).disabled).toBe(true);
		composer.value!.submit();
		expect(onSubmit).not.toHaveBeenCalled();
	});

	it("opens up when the prop turns off", async () => {
		const { root, composer, onSubmit, disabled } = await mount(EmailComposer);
		disabled.value = false;
		await settle();
		expect(body(root).getAttribute("contenteditable")).toBe("true");
		expect(attachButton(root).disabled).toBe(false);
		expect(sendButton(root).disabled).toBe(false);
		composer.value!.submit();
		expect(onSubmit).toHaveBeenCalledOnce();
	});

	it("reaches the comment composer too", async () => {
		const { root, composer, onSubmit } = await mount(CommentComposer);
		expect(body(root).getAttribute("contenteditable")).toBe("false");
		expect(sendButton(root).disabled).toBe(true);
		composer.value!.submit();
		expect(onSubmit).not.toHaveBeenCalled();
	});
});
