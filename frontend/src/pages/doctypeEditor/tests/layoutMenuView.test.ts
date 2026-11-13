// What the layout crumb's menu draws and what its rows do, the add dialog's refusal, and the
// address that names the open layout.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick, shallowRef, type App, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { editorBase, workingState } from "../editorModel";
import AddLayoutDialog from "../AddLayoutDialog.vue";
import LayoutMenu from "../LayoutMenu.vue";
import { useLayoutAddress } from "../layoutQuery";
import type { DesignCanvas } from "../designCanvas";
import { mountEditor } from "./editorFixture";
import { leadNote } from "./layoutsFixture";

const apps: App[] = [];
let editor: ReturnType<typeof mountEditor> | null = null;

afterEach(() => {
	apps.splice(0).forEach((app) => app.unmount());
	editor?.stop();
	editor = null;
	document.body.innerHTML = "";
});

async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

function mount(component: Component, props: Record<string, unknown>, setup?: (app: App) => void) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(component, props) }));
	setup?.(app);
	app.mount(root);
	apps.push(app);
	return root;
}

async function openMenu(state = leadNote()) {
	editor = mountEditor(state);
	const root = mount(LayoutMenu, { canvas: editor.canvas });
	await clickCrumb(root);
	return root;
}

/** Opens the menu and waits for its lazy rows' first import. */
async function clickCrumb(root: Element) {
	root.querySelector<HTMLButtonElement>("[data-layout-crumb]")!.click();
	await settle();
	for (let turn = 0; turn < 100 && !menu(); turn++) await new Promise((resolve) => setTimeout(resolve, 20));
}

const menu = () => document.body.querySelector("[data-layout-menu]");
const rowTexts = () =>
	[...document.body.querySelectorAll("[data-layout-row]")].map((row) => {
		const name = row.querySelector("span.block")!.textContent!.trim();
		const badge = row.textContent!.trim().slice(name.length).trim();
		return [row.getAttribute("data-layout-row"), `${name} · ${badge}`, Boolean(row.querySelector("[data-layout-open]"))];
	});

describe("the layout menu", () => {
	it("names the open layout on its crumb, and lists each type with its badge and conditional layouts", async () => {
		const root = await openMenu();
		expect(root.querySelector("[data-layout-crumb]")!.textContent).toContain("Details");
		expect(rowTexts()).toEqual([
			["Details", "Details · App layout", true],
			["Details/app:1", "Done · App layout", false],
			["Side Panel", "Side panel · Not set up", false],
			["Quick Entry", "Quick entry · From DocType fields", false],
			["New Record", "New record · Same as Details", false],
		]);
		expect(menu()!.querySelector("[data-layout-acts]")).toBeNull();
		expect(menu()!.querySelector("[data-layout-add]")).not.toBeNull();
	});

	it("opens a picked layout on the Editor tab and closes", async () => {
		const root = await openMenu();
		editor!.tab.value = "settings";
		document.body.querySelector<HTMLButtonElement>('[data-layout-row="Details/app:1"]')!.click();
		await settle();
		expect(editor!.canvas.openLayout.value).toEqual({ type: "Details", id: "app:1" });
		expect(editor!.tab.value).toBe("editor");
		expect(menu()).toBeNull();
		expect(root.querySelector("[data-layout-crumb]")!.textContent).toContain("Done");
	});

	it("ends with the open conditional layout's acts under its name and where it shows", async () => {
		editor = mountEditor(leadNote());
		editor.canvas.open({ type: "Details", id: "app:1" });
		const root = mount(LayoutMenu, { canvas: editor.canvas });
		await clickCrumb(root);
		const acts = menu()!.querySelector("[data-layout-acts]")!;
		expect(acts.textContent).toContain("Shows in the record page's main column when doc.status == 'Done'");
		expect([...acts.querySelectorAll("[data-layout-act]")].map((act) => act.getAttribute("data-layout-act"))).toEqual([
			"edit_condition",
			"rename",
			"delete",
		]);
		acts.querySelector<HTMLButtonElement>('[data-layout-act="delete"]')!.click();
		await settle();
		expect(editor.edits.staged.value.map((edit) => edit.act)).toEqual(["layouts.delete"]);
	});

	it("gives a child table Details only, with its note", async () => {
		const state = leadNote();
		await openMenu({ ...state, definition: { ...state.definition, istable: 1 } });
		const types = rowTexts().filter(([key]) => !String(key).includes("/"));
		expect(types.map(([key]) => key)).toEqual(["Details"]);
		expect(menu()!.textContent).toContain("A child table's rows use Details only");
	});
});

describe("the add layout dialog", () => {
	it("refuses a second default layout of a type, and adds one with a condition", async () => {
		const closed: unknown[] = [];
		const working = workingState(editorBase(leadNote()), []);
		const types = [{ value: "Details", label: "Details" }];
		const root = mount(AddLayoutDialog, { working, types, type: "Details", close: (one: unknown) => closed.push(one) });
		await settle();
		const submit = () => root.querySelector<HTMLButtonElement>("[data-add-layout-submit]")!.click();
		submit();
		await settle();
		expect(root.querySelector("[data-add-layout-refusal]")?.textContent).toBeTruthy();
		expect(closed).toEqual([]);
		const condition = root.querySelector<HTMLInputElement>("[data-add-layout-condition] input, input[data-add-layout-condition]")!;
		condition.value = "doc.partner";
		condition.dispatchEvent(new Event("input"));
		submit();
		await settle();
		expect(closed).toEqual([{ type: "Details", title: "", condition: "doc.partner", start: "copy" }]);
	});
});

describe("the address", () => {
	async function mountAddress(path: string) {
		editor = mountEditor(leadNote());
		const canvas = shallowRef<DesignCanvas>(editor.canvas);
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [{ path: "/:rest(.*)*", component: { render: () => null } }],
		});
		await router.push(path);
		mount(
			defineComponent({
				setup() {
					useLayoutAddress(() => canvas.value);
					return () => null;
				},
			}),
			{},
			(app) => app.use(router)
		);
		await settle();
		return { router, canvas: editor.canvas };
	}

	it("writes the open layout and keeps the other keys", async () => {
		const { router, canvas } = await mountAddress("/doctype/lead-note?mode=customize&table=items");
		canvas.open({ type: "Details", id: "app:1" });
		await settle();
		expect(router.currentRoute.value.query).toEqual({ mode: "customize", table: "items", layout: "details", row: "app:1" });
	});

	it("opens the layout a changed address names", async () => {
		const { router, canvas } = await mountAddress("/doctype/lead-note");
		await router.replace({ query: { layout: "quick-entry" } });
		await settle();
		expect(canvas.openLayout.value).toEqual({ type: "Quick Entry" });
	});
});
