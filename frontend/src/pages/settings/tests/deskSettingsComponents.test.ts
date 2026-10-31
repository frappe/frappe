// Desk's own settings components, as the build discovers them: the theme, the photo, the language
// and time zone over the session user's binding, the session defaults read and saved by method, and
// the password change.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, reactive, type App, type Component } from "vue";

const fake = vi.hoisted(() => ({ toastError: vi.fn() }));
vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: vi.fn(), error: fake.toastError },
}));

import { useColorScheme } from "frappe-ui";
import { getFieldComponent, registerFieldType } from "@framework/ui/FormLayout";
import { resetSession, setSession } from "@framework/ui/useSession";
import { settingsComponentFor } from "@/contributions/registry";

const NAMES = [
	"theme",
	"profile-photo",
	"language-and-time-zone",
	"session-defaults",
	"change-password",
];
const SESSION_DEFAULTS = "frappe.core.doctype.session_default_settings.session_default_settings";
const UPDATE_PASSWORD = "frappe.core.doctype.user.user.update_password";

/** A field control that shows what it was handed and commits a value on click. */
const drawn: Record<
	string,
	{ options?: string; placeholder?: string; modelValue: unknown; commit: (value: unknown) => void }
> = {};
const FieldProbe = defineComponent({
	props: { field: { type: Object, required: true }, modelValue: null },
	emits: ["update:modelValue", "change"],
	setup(props, { emit }) {
		return () => {
			drawn[props.field.fieldname] = {
				options: props.field.options,
				placeholder: props.field.placeholder,
				modelValue: props.modelValue,
				commit: (value) => {
					emit("update:modelValue", value);
					emit("change", value);
				},
			};
			return h("span", { "data-probe": props.field.fieldname });
		};
	},
});

let mounted: App | undefined;
let methods: Record<string, (body: any) => unknown>;
let originals: Record<string, Component>;

beforeEach(() => {
	originals = { Link: getFieldComponent("Link"), Autocomplete: getFieldComponent("Autocomplete") };
	registerFieldType("Link", FieldProbe);
	registerFieldType("Autocomplete", FieldProbe);
	for (const key of Object.keys(drawn)) delete drawn[key];
	methods = {};
	vi.stubGlobal(
		"fetch",
		vi.fn(async (url: string, init?: RequestInit) => {
			const path = decodeURIComponent(new URL(url, "http://x").pathname);
			if (path === "/api/v2/document/Language")
				return new Response(JSON.stringify({ data: [{ name: "en", language_name: "English" }] }));
			const method = path.split("/method/")[1];
			const body = init?.body ? JSON.parse(String(init.body)) : {};
			const reply = methods[method]?.(body);
			if (reply instanceof Response) return reply;
			return new Response(JSON.stringify({ data: reply ?? null }));
		})
	);
	fake.toastError.mockReset();
	document.body.innerHTML = "";
});

afterEach(() => {
	mounted?.unmount();
	mounted = undefined;
	for (const [fieldtype, component] of Object.entries(originals))
		registerFieldType(fieldtype, component);
	vi.unstubAllGlobals();
	resetSession();
	useColorScheme().setColorScheme("light");
});

async function settle() {
	for (let turn = 0; turn < 8; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function mount(name: string, bindings: Record<string, unknown> = {}) {
	const { default: component } = (await settingsComponentFor("frappe", name)!()) as {
		default: Component;
	};
	mounted = createApp(component, { bindings });
	mounted.mount(document.body.appendChild(document.createElement("div")));
	await settle();
}

function userBinding(values: Record<string, unknown>) {
	return reactive({
		doc: { name: "jane@example.com", email: "jane@example.com", ...values } as Record<string, any>,
		loading: false,
		error: "",
		commit: vi.fn(async () => {}),
	});
}

function type(fieldname: string, value: string) {
	const input = document.querySelector<HTMLInputElement>(`[data-fieldname="${fieldname}"] input`)!;
	input.value = value;
	input.dispatchEvent(new Event("input", { bubbles: true }));
}

function button(label: string): HTMLButtonElement {
	return Array.from(document.querySelectorAll("button")).find(
		(one) => one.textContent?.trim() === label
	)!;
}

describe("desk's settings components", () => {
	it("are found by the build under the framework's name", () => {
		for (const name of NAMES) expect(settingsComponentFor("frappe", name)).toBeTypeOf("function");
	});

	it("theme: one row whose select shows the scheme in use, with its icon, and applies a pick", async () => {
		const { colorScheme, setColorScheme } = useColorScheme();
		setColorScheme("light");
		await mount("theme");
		const trigger = document.querySelector<HTMLElement>("button[role='combobox']")!;

		expect(trigger.textContent).toContain("Light");
		expect(trigger.querySelector(".lucide-sun")).toBeTruthy();

		trigger.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 }));
		trigger.click();
		await settle();
		const dark = Array.from(document.querySelectorAll<HTMLElement>("[role='option']")).find(
			(option) => option.textContent?.includes("Dark")
		)!;
		expect(dark.querySelector(".lucide-moon")).toBeTruthy();
		dark.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0, pointerType: "mouse" }));
		dark.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, button: 0, pointerType: "mouse" }));
		dark.click();
		await settle();

		expect(colorScheme.value).toBe("dark");
		expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
		expect(trigger.textContent).toContain("Dark");
	});

	it("profile photo: shows the person and removes the photo through the binding", async () => {
		const user = userBinding({ full_name: "Jane Doe", user_image: "/files/jane.png" });
		await mount("profile-photo", { user });

		expect(document.body.textContent).toContain("Jane Doe");
		expect(document.body.textContent).toContain("jane@example.com");
		expect(button("Change photo")).toBeTruthy();

		button("Remove").click();
		await settle();

		expect(user.doc.user_image).toBeNull();
		expect(user.commit).toHaveBeenCalledOnce();
		expect(button("Upload photo")).toBeTruthy();
		expect(button("Remove")).toBeUndefined();
	});

	it("language and time zone: the time zones come from the server, and a pick commits", async () => {
		methods["frappe.core.doctype.user.user.get_timezones"] = () => ({
			timezones: ["Asia/Kolkata", "Europe/Paris"],
		});
		const user = userBinding({ language: "en", time_zone: "Asia/Kolkata" });
		await mount("language-and-time-zone", { user });

		expect(drawn.language).toMatchObject({ options: "Language", modelValue: "en" });
		expect(drawn.time_zone).toMatchObject({
			options: "Asia/Kolkata\nEurope/Paris",
			modelValue: "Asia/Kolkata",
		});

		drawn.time_zone.commit("Europe/Paris");
		await settle();

		expect(user.doc.time_zone).toBe("Europe/Paris");
		expect(user.commit).toHaveBeenCalledOnce();
	});

	it("language and time zone: a refused save shows under its own row only", async () => {
		const user = userBinding({ language: "en", time_zone: "Asia/Kolkata" });
		user.commit.mockImplementation(async () => {
			user.error = "Not a zone";
		});
		await mount("language-and-time-zone", { user });

		drawn.time_zone.commit("Mars/Olympus");
		await settle();

		const rows = document.querySelectorAll<HTMLElement>("[data-fieldname]");
		expect(rows[1].textContent).toContain("Not a zone");
		expect(rows[0].textContent).not.toContain("Not a zone");
	});

	it("language and time zone: an empty language shows the site default as its placeholder", async () => {
		setSession({
			user: { name: "jane@example.com" },
			roles: [],
			lang: "en",
			timezone: "Asia/Kolkata",
			defaults: { language: "en" },
		} as unknown as Parameters<typeof setSession>[0]);
		await mount("language-and-time-zone", { user: userBinding({ language: null }) });

		expect(drawn.language).toMatchObject({
			modelValue: null,
			placeholder: "English (site default)",
		});
	});

	it("session defaults: one Link per default, and a change saves them all", async () => {
		const saved = vi.fn(() => "success");
		methods[`${SESSION_DEFAULTS}.get_session_default_values`] = () =>
			JSON.stringify([
				{ fieldname: "company", fieldtype: "Link", options: "Company", label: "Default Company", default: "Acme" },
				{ fieldname: "project", fieldtype: "Link", options: "Project", label: "Default Project", default: null },
			]);
		methods[`${SESSION_DEFAULTS}.set_session_default_values`] = saved;
		await mount("session-defaults");

		expect(document.body.textContent).toContain("Default Company");
		expect(drawn.company).toMatchObject({ options: "Company", modelValue: "Acme" });

		drawn.project.commit("Apollo");
		await settle();

		expect(saved).toHaveBeenCalledWith({
			default_values: { company: "Acme", project: "Apollo" },
		});
		expect(fake.toastError).not.toHaveBeenCalled();
	});

	it("session defaults: says so when the site sets none, and names a refused save", async () => {
		methods[`${SESSION_DEFAULTS}.get_session_default_values`] = () => "[]";
		await mount("session-defaults");
		expect(document.body.textContent).toContain("This site sets no session defaults.");
		mounted!.unmount();

		methods[`${SESSION_DEFAULTS}.get_session_default_values`] = () =>
			JSON.stringify([
				{ fieldname: "company", fieldtype: "Link", options: "Company", label: "Default Company", default: "" },
			]);
		methods[`${SESSION_DEFAULTS}.set_session_default_values`] = () => null;
		await mount("session-defaults");
		drawn.company.commit("Acme");
		await settle();

		expect(fake.toastError).toHaveBeenCalledWith("Your session defaults did not save");
	});

	it("change password: sends both passwords, logs out other sessions, and reloads", async () => {
		const reload = vi.fn();
		vi.stubGlobal("location", { ...window.location, reload });
		const changed = vi.fn(() => "/desk");
		methods[UPDATE_PASSWORD] = changed;
		await mount("change-password");

		type("current", "old secret");
		type("next", "Tr1cky horse battery");
		type("confirm", "Tr1cky horse");
		await settle();
		expect(document.body.textContent).toContain("The new passwords do not match");
		expect(button("Change password").disabled).toBe(true);

		type("confirm", "Tr1cky horse battery");
		await settle();
		button("Change password").click();
		await settle();

		expect(changed).toHaveBeenCalledWith({
			old_password: "old secret",
			new_password: "Tr1cky horse battery",
			logout_all_sessions: 1,
		});
		expect(reload).toHaveBeenCalledOnce();
	});

	it("change password: a refused change shows the server's message and does not reload", async () => {
		const reload = vi.fn();
		vi.stubGlobal("location", { ...window.location, reload });
		methods[UPDATE_PASSWORD] = () =>
			new Response(
				JSON.stringify({
					errors: [{ type: "AuthenticationError", message: "Incorrect User or Password" }],
				}),
				{ status: 401 }
			);
		await mount("change-password");

		type("current", "wrong");
		type("next", "Tr1cky horse battery");
		type("confirm", "Tr1cky horse battery");
		await settle();
		button("Change password").click();
		await settle();

		expect(document.querySelector("[role='alert']")?.textContent).toBe(
			"Incorrect User or Password"
		);
		expect(reload).not.toHaveBeenCalled();
		expect(button("Change password").disabled).toBe(false);
	});
});
