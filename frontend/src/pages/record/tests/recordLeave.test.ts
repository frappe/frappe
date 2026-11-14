// Leaving a record for a page with no doctype in its address, as the DocType editor's: the shell's act keys still read the record's header on the way out.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView } from "vue-router";

vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent, h } = await import("vue");
	return {
		pageGutter: "px-[--page-gutter]",
		default: defineComponent({
			setup: (_, { slots }) => () => h("div", [h("header", slots.header?.()), slots.default?.()]),
		}),
	};
});
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/doctypeEditor/DoctypeEditor.vue", () => ({ default: { render: () => h("p", "editor") } }));

import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import { ActKeys } from "@/shell/actKeys";
import { resetFormLayouts } from "@/recordPage/formLayoutSource/useFormLayout";
import { resetRegistry } from "@/recordPage/registry";
import { resetViewMemory } from "../viewMemory";

registerStandardPages(standardPages);
await standardPages.record();
await standardPages.doctypeEditor();

const META = { name: "Note", fields: [{ fieldname: "title", fieldtype: "Data", label: "Title" }] };

function answer(path: string): unknown {
	if (path === "/api/v2/doctype/Note/meta") return { data: META };
	if (path.endsWith(".get_form_layouts")) return { data: { layouts: [], fallback: [] } };
	if (path.endsWith(".get_client_scripts")) return { data: { scripts: [], can_write: false } };
	if (path.endsWith("/activity")) return { data: { activities: [], next: null } };
	if (path.startsWith("/api/v2/document/Note/"))
		return { data: { doctype: "Note", name: "N-1", title: "First" }, permissions: { read: 1 } };
	return { data: null };
}

const boot = {
	app: "frappe",
	shell_base: "/apps/frappe",
	prefixes: { frappe: { app: "frappe", modular: false } },
	session: { user: { name: "test@example.com", email: "test@example.com" }, roles: [] },
} as unknown as Boot;
const addresses = new Addresses({
	doctypes: { Note: ["note", "desk"], DocType: ["doctype", "core"] },
	modules: { desk: "Desk", core: "Core" },
});
const apps: ReturnType<typeof createApp>[] = [];

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: string) => {
			const body = answer(decodeURIComponent(new URL(String(input), "http://x").pathname));
			return new Response(JSON.stringify(body), { status: 200 });
		})
	);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
	resetRegistry();
	clearDataCache();
	resetViewMemory();
});

async function settle() {
	for (let turn = 0; turn < 10; turn++) {
		await nextTick();
		await new Promise((resolve) => setTimeout(resolve));
	}
}

async function mountRecord() {
	const router = createShellRouter(boot, addresses);
	registerShell({ boot, addresses, router });
	await router.push("/note/N-1");
	const app = createApp(defineComponent({ render: () => [h(RouterView), h(ActKeys)] }));
	app.use(router);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.provide("socket", { on() {}, off() {}, emit() {} });
	app.mount(document.body.appendChild(document.createElement("div")));
	apps.push(app);
	await settle();
	return router;
}

it("opens the DocType editor from a record without a routing error", async () => {
	const router = await mountRecord();
	const logged = [vi.spyOn(console, "error"), vi.spyOn(console, "warn")];
	const failures: unknown[] = [];
	const failed = (error: unknown) => void failures.push(error);
	apps[0].config.errorHandler = failed;

	await router.push("/doctype/Note?mode=customize");
	await settle();

	expect(router.currentRoute.value.name).toBe("doctype-editor");
	expect(document.body.textContent).toContain("editor");
	const messages = [...failures, ...logged.flatMap((spy) => spy.mock.calls.flat())].map(String);
	expect(messages.filter((message) => message.includes("routeFor"))).toEqual([]);
});
