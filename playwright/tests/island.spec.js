import { test, expect } from "../support";

const ISLAND = "frappe.playwright_fixture";

const FIXTURE_MODULE = `
	export function mount(el, context) {
		window.__island_mounts = (window.__island_mounts || 0) + 1;
		window.__island_context = context;

		const host = document.createElement("div");
		host.className = "fixture-island";
		el.appendChild(host);

		const root = host.attachShadow({ mode: "open" });
		const node = document.createElement("div");
		node.className = "fixture";
		root.append(node);

		let props = { ...(context.props || {}) };
		const render = () => (node.textContent = props.label || "");
		render();

		context.props?.onReady?.(context.host);

		return Promise.all((context.styles || []).map(adopt)).then((sheets) => {
			root.adoptedStyleSheets = sheets;
			return {
				update(next) {
					props = { ...props, ...next };
					render();
				},
				unmount() {
					window.__island_unmounts = (window.__island_unmounts || 0) + 1;
					host.remove();
				},
			};
		});
	}

	function adopt(url) {
		return fetch(url)
			.then((response) => response.text())
			.then((css) => {
				const sheet = new CSSStyleSheet();
				sheet.replaceSync(css);
				return sheet;
			});
	}
`;

const FIXTURE_CSS = `.fixture { color: rgb(1, 2, 3); }`;

async function register_fixture(page) {
	await page.evaluate(
		([island, module, css]) => {
			const blob_url = (source, type) => URL.createObjectURL(new Blob([source], { type }));

			frappe.boot.assets_json[`${island}.island.js`] = blob_url(module, "text/javascript");
			frappe.boot.assets_json[`${island}.island.css`] = blob_url(css, "text/css");
			frappe.boot.ui_islands = [...(frappe.boot.ui_islands || []), island];
			window.__island_mounts = 0;
			window.__island_unmounts = 0;
		},
		[ISLAND, FIXTURE_MODULE, FIXTURE_CSS]
	);
}

async function host_element(page, id) {
	await page.evaluate((id) => {
		const el = document.createElement("div");
		el.id = id;
		document.querySelector("#body").appendChild(el);
	}, id);
	return page.locator(`#${id}`);
}

const shadow_text = (el) =>
	el.querySelector(".fixture-island").shadowRoot.querySelector(".fixture").textContent;

test.describe("Island", () => {
	test.beforeEach(async ({ page, desk }) => {
		await page.goto("/app/website");
		await desk.ready();
		await register_fixture(page);
	});

	test("resolves a declared name and mounts what it names", async ({ page }) => {
		const el = await host_element(page, "island-1");
		await el.evaluate(async (el, island) => {
			await frappe.ui.mount_island(island, el, { label: "hello" }).ready;
		}, ISLAND);

		expect(await page.evaluate(() => window.__island_mounts)).toBe(1);
		expect(await el.evaluate(shadow_text)).toBe("hello");
	});

	test("hands the island desk's context", async ({ page }) => {
		const el = await host_element(page, "island-2");
		const host = await el.evaluate(async (el, island) => {
			await frappe.ui.mount_island(island, el, {}).ready;
			const host = window.__island_context.host;
			return {
				user: host.user,
				session_user: frappe.session.user,
				locale: typeof host.locale,
				base_url: typeof host.base_url,
				navigate: typeof host.navigate,
			};
		}, ISLAND);

		expect(host.user).toBe(host.session_user);
		expect(host.locale).toBe("string");
		expect(host.base_url).toBe("string");
		expect(host.navigate).toBe("function");
	});

	test("hands the island its own stylesheet", async ({ page }) => {
		const el = await host_element(page, "island-3");
		const result = await el.evaluate(async (el, island) => {
			await frappe.ui.mount_island(island, el, {}).ready;
			const root = el.querySelector(".fixture-island").shadowRoot;
			return {
				styles: window.__island_context.styles,
				css: frappe.boot.assets_json[`${island}.island.css`],
				selector: root.adoptedStyleSheets[0].cssRules[0].selectorText,
			};
		}, ISLAND);

		expect(result.styles).toEqual([result.css]);
		expect(result.selector).toBe(".fixture");
	});

	test("hands the island the listeners in its props", async ({ page }) => {
		const el = await host_element(page, "island-4");
		const ready_calls = await el.evaluate(async (el, island) => {
			let calls = 0;
			await frappe.ui.mount_island(island, el, { onReady: () => calls++ }).ready;
			return calls;
		}, ISLAND);

		expect(ready_calls).toBe(1);
	});

	test("update(props) reaches the island without re-mounting it", async ({ page }) => {
		const el = await host_element(page, "island-5");
		await el.evaluate(async (el, island) => {
			const mounted = await frappe.ui.mount_island(island, el, { label: "before" }).ready;
			mounted.update({ label: "after" });
		}, ISLAND);

		expect(await el.evaluate(shadow_text)).toBe("after");
		expect(await page.evaluate(() => window.__island_mounts)).toBe(1);
	});

	test("unmounts idempotently", async ({ page }) => {
		const el = await host_element(page, "island-6");
		await el.evaluate(async (el, island) => {
			const mounted = await frappe.ui.mount_island(island, el, {}).ready;
			mounted.unmount();
			mounted.unmount();
		}, ISLAND);

		expect(await page.evaluate(() => window.__island_unmounts)).toBe(1);
		await expect(el.locator(".fixture-island")).toHaveCount(0);
	});

	test("replaces the island already in a target", async ({ page }) => {
		const el = await host_element(page, "island-7");
		await el.evaluate(async (el, island) => {
			await frappe.ui.mount_island(island, el, { label: "first" }).ready;
			await frappe.ui.mount_island(island, el, { label: "second" }).ready;
		}, ISLAND);

		expect(await page.evaluate(() => window.__island_unmounts)).toBe(1);
		await expect(el.locator(".fixture-island")).toHaveCount(1);
		expect(await el.evaluate(shadow_text)).toBe("second");
	});

	test("explains an island name this site does not have", async ({ page }) => {
		const el = await host_element(page, "island-8");
		const message = await el.evaluate((el) =>
			frappe.ui.mount_island("nosuchapp.nosuchisland", el, {}).ready.then(
				() => {
					throw new Error("expected mount_island to reject");
				},
				(e) => e.message
			)
		);

		expect(message).toContain("is not on this site");
	});

	test("explains a registered island whose app has not been built", async ({ page }) => {
		const el = await host_element(page, "island-9");
		const message = await el.evaluate((el) => {
			frappe.boot.ui_islands.push("frappe.unbuilt");
			return frappe.ui.mount_island("frappe.unbuilt", el, {}).ready.then(
				() => {
					throw new Error("expected mount_island to reject");
				},
				(e) => e.message
			);
		});

		expect(message).toContain("is not on this site");
	});

	test("leaves classic bundles on the page working", async ({ page }) => {
		const el = await host_element(page, "island-10");
		const title = await el.evaluate(async (el, island) => {
			await frappe.ui.mount_island(island, el, {}).ready;
			await frappe.require("dialog.bundle.js");

			const dialog = new frappe.ui.Dialog({ title: "classic" });
			dialog.show();
			const title = dialog.$wrapper.find(".modal-title").text();
			dialog.hide();
			return title;
		}, ISLAND);

		expect(title).toContain("classic");
	});
});
