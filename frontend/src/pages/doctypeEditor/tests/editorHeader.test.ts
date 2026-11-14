// The editor header's crumbs while a child table is open: the parent's crumb leads back to its editor.
import { afterEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import EditorHeader from "../EditorHeader.vue";
import type { EditorMode } from "../pendingEdits";

const apps: App[] = [];

afterEach(() => {
	apps.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
});

function mountHeader(mode: EditorMode, openParent: () => void) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:any(.*)*", name: "list", component: { render: () => null } }],
	});
	registerShell({
		boot: { app: "frappe", shell_base: "/apps/frappe", prefixes: { frappe: { app: "frappe", modular: false } } } as unknown as Boot,
		addresses: new Addresses({ doctypes: { DocType: ["doctype", "core"], "Walk Order": ["walk-order", "core"] }, modules: { core: "Core" } }),
		router,
	});
	const props = {
		doctype: "Walk Order",
		canvas: null,
		dirty: false,
		canUndo: false,
		canRedo: false,
		canSave: false,
		saving: false,
		mode,
		modes: [mode],
		developerMode: false,
		tab: "editor",
		childCrumbs: [{ label: "Items", onClick: () => {} }, { label: "Walk Order Item" }],
		onOpenParent: openParent,
	};
	const root = document.body.appendChild(document.createElement("div"));
	const app = createApp(defineComponent({ render: () => h(EditorHeader, props) }));
	app.use(router);
	app.mount(root);
	apps.push(app);
	return root;
}

function crumb(root: Element, label: string) {
	return [...root.querySelectorAll<HTMLElement>("[data-crumbs] > *")].find((one) => one.textContent!.trim() === label)!;
}

it.each([
	["Design", "Walk Order"],
	["Customize", "Customize"],
] as const)("opens the parent's editor from the parent's crumb in %s", async (mode, label) => {
	const openParent = vi.fn();
	const root = mountHeader(mode, openParent);
	await nextTick();

	crumb(root, label).click();

	expect(openParent).toHaveBeenCalledTimes(1);
});
