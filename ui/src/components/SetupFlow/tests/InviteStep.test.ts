import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";

const ROLES = [
	{ label: "Member", value: "Member" },
	{ label: "Manager", value: "Manager" },
];

let app: App | null = null;

async function mountStep(
	props: Record<string, unknown> = {},
	slots: Record<string, unknown> = {}
) {
	const { default: InviteStep } = await import("../InviteStep.vue");
	const done = vi.fn();
	const skip = vi.fn();
	const back = vi.fn();
	const invitees = vi.fn();
	const send = (props.send as () => Promise<unknown>) ?? vi.fn().mockResolvedValue(undefined);
	const el = document.createElement("div");
	document.body.appendChild(el);
	app = createApp({
		render: () =>
			h(
				InviteStep,
				{
					roles: ROLES,
					...props,
					send,
					onDone: done,
					onSkip: skip,
					onBack: back,
					onInvitees: invitees,
				},
				slots
			),
	});
	app.mount(el);
	await nextTick();
	return { el, done, skip, back, invitees, send };
}

const settle = async () => {
	await new Promise((resolve) => setTimeout(resolve, 0));
	await nextTick();
};

const emails = (el: HTMLElement) =>
	Array.from(el.querySelectorAll<HTMLInputElement>('input[type="email"]'));
// frappe-ui's select shows the chosen label in its trigger button.
const chosenRoles = (el: HTMLElement) =>
	Array.from(el.querySelectorAll("button"))
		.map((b) => b.textContent?.trim())
		.filter((label) => label === "Member" || label === "Manager");

async function type(el: HTMLElement, row: number, value: string) {
	const input = emails(el)[row];
	input.value = value;
	input.dispatchEvent(new Event("input", { bubbles: true }));
	await nextTick();
}

const button = (el: HTMLElement, label: string) =>
	Array.from(el.querySelectorAll("button")).find(
		(b) => b.textContent?.trim() === label || b.getAttribute("aria-label") === label,
	) as HTMLButtonElement | undefined;

afterEach(() => {
	app?.unmount();
	app = null;
	document.body.innerHTML = "";
});

describe("InviteStep", () => {
	it("starts with two rows, the first with the suggested role", async () => {
		const { el } = await mountStep({ firstRole: "Manager" });
		expect(emails(el)).toHaveLength(2);
		expect(chosenRoles(el)).toEqual(["Manager", "Member"]);
	});

	it("moves the first row to a new suggestion until a name is typed there", async () => {
		const { default: InviteStep } = await import("../InviteStep.vue");
		const firstRole = ref("Member");
		const el = document.createElement("div");
		document.body.appendChild(el);
		app = createApp({
			render: () => h(InviteStep, { roles: ROLES, firstRole: firstRole.value, send: vi.fn() }),
		});
		app.mount(el);
		await nextTick();

		firstRole.value = "Manager";
		await nextTick();
		await nextTick();
		expect(chosenRoles(el)[0]).toBe("Manager");

		await type(el, 0, "a@example.com");
		firstRole.value = "Member";
		await nextTick();
		await nextTick();
		expect(chosenRoles(el)[0]).toBe("Manager");
	});

	it("sends one call per role and reports how many were invited", async () => {
		const send = vi.fn().mockResolvedValueOnce(2).mockResolvedValueOnce(undefined);
		const { el, done } = await mountStep({ send, firstRole: "Manager" });
		await type(el, 0, "a@example.com");
		await type(el, 1, "b@example.com");
		button(el, "Add another")!.click();
		await nextTick();
		await type(el, 2, "c@example.com");

		button(el, "Send invites")!.click();
		await settle();

		expect(send).toHaveBeenNthCalledWith(1, "Manager", ["a@example.com"]);
		expect(send).toHaveBeenNthCalledWith(2, "Member", ["b@example.com", "c@example.com"]);
		expect(done).toHaveBeenCalledWith({ invited: 4, roles: ["Manager", "Member"] });
	});

	it("will not send an invalid or repeated email", async () => {
		const { el, send } = await mountStep();
		await type(el, 0, "not-an-email");
		expect(el.textContent).toContain("Enter a valid email address");
		expect(button(el, "Send invites")!.disabled).toBe(true);

		await type(el, 0, "a@example.com");
		await type(el, 1, "A@example.com");
		expect(el.textContent).toContain("This email is already in the list");
		expect(button(el, "Send invites")!.disabled).toBe(true);
		expect(send).not.toHaveBeenCalled();
	});

	it("keeps one empty row when the last one is removed", async () => {
		const { el } = await mountStep();
		await type(el, 0, "a@example.com");
		button(el, "Remove 2")!.click();
		await nextTick();
		button(el, "Remove 1")!.click();
		await nextTick();
		expect(emails(el)).toHaveLength(1);
		expect(emails(el)[0].value).toBe("");
	});

	it("locks what was sent and sends only the rest when a role fails", async () => {
		const send = vi
			.fn()
			.mockResolvedValueOnce(1)
			.mockRejectedValueOnce({ messages: ["Mail is down"] })
			.mockResolvedValueOnce(1);
		const { el, done } = await mountStep({ send, firstRole: "Manager" });
		await type(el, 0, "a@example.com");
		await type(el, 1, "b@example.com");

		button(el, "Send invites")!.click();
		await settle();

		expect(el.textContent).toContain("Mail is down");
		expect(emails(el).map((input) => input.disabled)).toEqual([true, false]);
		expect(el.textContent).toContain("Sent");
		expect(button(el, "Remove 1")).toBeUndefined();
		expect(done).not.toHaveBeenCalled();

		button(el, "Send invites")!.click();
		await settle();
		expect(send).toHaveBeenLastCalledWith("Member", ["b@example.com"]);
		expect(done).toHaveBeenCalledWith({ invited: 2, roles: ["Manager", "Member"] });
	});

	it("stays on the step and names who could not be invited", async () => {
		const send = vi.fn().mockResolvedValue({ failed: ["B@example.com"] });
		const { el, done } = await mountStep({
			send,
			labels: { failedWho: (who: string) => `Could not invite ${who}: their account is disabled.` },
		});
		await type(el, 0, "a@example.com");
		await type(el, 1, "b@example.com");

		button(el, "Send invites")!.click();
		await settle();

		expect(el.textContent).toContain("1 invite could not be sent");
		expect(el.textContent).toContain("Could not invite b@example.com: their account is disabled.");
		expect(emails(el).map((input) => input.disabled)).toEqual([true, false]);
		expect(done).not.toHaveBeenCalled();

		button(el, "Remove 2")!.click();
		await nextTick();
		button(el, "Continue")!.click();
		expect(done).toHaveBeenCalledWith({ invited: 1, roles: ["Member"] });
	});

	it("lets the app show its own message for an error", async () => {
		const send = vi.fn().mockRejectedValue({ messages: ["No email account"] });
		const { el } = await mountStep(
			{ send },
			{ error: ({ message }: { message: string }) => h("a", `${message}. Connect email`) }
		);
		await type(el, 0, "a@example.com");

		button(el, "Send invites")!.click();
		await settle();

		expect(el.querySelector("a")?.textContent).toBe("No email account. Connect email");
	});

	it("shares the valid emails as they are typed", async () => {
		const { el, invitees } = await mountStep();
		await type(el, 0, "a@example.com");
		await type(el, 1, "b@");
		expect(invitees).toHaveBeenLastCalledWith([{ email: "a@example.com", role: "Member" }]);
	});

	it("skips, and shows Back only when asked to", async () => {
		const { el, skip } = await mountStep();
		expect(button(el, "Back")).toBeUndefined();
		button(el, "Skip this step")!.click();
		expect(skip).toHaveBeenCalled();
		app!.unmount();

		const withBack = await mountStep({ canGoBack: true });
		button(withBack.el, "Back")!.click();
		expect(withBack.back).toHaveBeenCalled();
	});
});
