// The permissions picker's roles: loading while they load, and a failure with Try again, not "No results".
import { afterEach, expect, it, vi } from "vitest";
import { createApp, h } from "vue";
import SettingsPermissions from "../SettingsPermissions.vue";
import { SettingsViewKey } from "../settingsView";

const { listDocuments } = vi.hoisted(() => ({ listDocuments: vi.fn() }));
vi.mock("@framework/ui/api", async (original) => ({
	...(await original<typeof import("@framework/ui/api")>()),
	listDocuments,
}));

const view = {
	customize: false,
	siteOverridesPermissions: false,
	kind: "standard",
	settings: { sitePermissions: false, permissionsRefusal: "", permissions: [] },
	errors: () => [],
	permission: vi.fn(),
	customizeRoute: () => null,
};

let app: ReturnType<typeof createApp> | null = null;

afterEach(() => {
	app?.unmount();
	app = null;
	document.body.innerHTML = "";
	listDocuments.mockReset();
});

function mount() {
	const root = document.createElement("div");
	document.body.appendChild(root);
	app = createApp({ render: () => h(SettingsPermissions, { row: { key: "permissions" } as never }) });
	app.provide(SettingsViewKey, view as never);
	app.mount(root);
	return root;
}

const failed = (root: Element) => root.querySelector("[data-roles-failed]");

it("shows the picker while the roles load, and no failure", async () => {
	listDocuments.mockReturnValue(new Promise(() => {}));
	const root = mount();
	await vi.waitFor(() => expect(root.querySelector("[data-perm-add]")).not.toBeNull());
	expect(failed(root)).toBeNull();
});

it("says the roles failed to load and reads them again on Try again", async () => {
	listDocuments.mockRejectedValueOnce(new Error("Offline"));
	listDocuments.mockResolvedValueOnce({ data: [{ name: "Sales User" }] });
	const root = mount();
	await vi.waitFor(() => expect(failed(root)).not.toBeNull());
	expect(failed(root)!.textContent).toContain("Could not load the roles.");
	expect(root.querySelector("[data-perm-add]")).toBeNull();
	failed(root)!.querySelector("button")!.click();
	await vi.waitFor(() => expect(failed(root)).toBeNull());
	expect(listDocuments).toHaveBeenCalledTimes(2);
	expect(root.querySelector("[data-perm-add]")).not.toBeNull();
});
