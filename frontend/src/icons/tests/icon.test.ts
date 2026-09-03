// What an authored icon name draws, and what an unknown one does not.
//
// Mounted with Vue's own `createApp` into happy-dom: this package has no
// `@vue/test-utils`, and a shared devDependency for one component is a cost every app pays.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";

import Icon from "../Icon.vue";
import { loadSprite, resetSprite } from "../sprite";

const SPRITE =
	'<svg id="frappe-symbols" style="display:none">' +
	'<symbol id="icon-users" viewBox="0 0 24 24"><circle cx="9" cy="7" r="4"/></symbol>' +
	"</svg>";

function stubFetch() {
	vi.stubGlobal(
		"fetch",
		vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve(SPRITE) })
	);
}

function mount(props: { name?: string; reserve?: boolean }) {
	const host = document.createElement("div");
	document.body.appendChild(host);
	createApp({ render: () => h(Icon, props) }).mount(host);
	return host;
}

beforeEach(() => {
	document.body.innerHTML = "";
	resetSprite();
	stubFetch();
});

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe("a name in the sprite", () => {
	it("draws the symbol", async () => {
		await loadSprite();

		const host = mount({ name: "users" });

		expect(host.querySelector("use")?.getAttribute("href")).toBe("#icon-users");
	});

	it("is hidden from a screen reader", async () => {
		// It sits beside the label it illustrates, so naming it reads the row twice.
		await loadSprite();

		const host = mount({ name: "users" });

		expect(host.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
	});

	it("appears when the sprite lands, without another render", async () => {
		// `main.ts` fires the sprite without awaiting it, so a rail paints before it lands.
		const host = mount({ name: "users" });
		expect(host.querySelector("use")).toBeNull();

		await loadSprite();
		await nextTick();

		expect(host.querySelector("use")?.getAttribute("href")).toBe("#icon-users");
	});
});

describe("an emoji", () => {
	it("is drawn as text, not looked up in the sprite", async () => {
		// The other value `fieldtype: Icon` stores; the field sets `options: Emojis`.
		await loadSprite();

		const host = mount({ name: "🚀" });

		expect(host.querySelector("svg")).toBeNull();
		expect(host.textContent).toBe("🚀");
	});
});

describe("a name the sprite does not hold", () => {
	it("draws nothing and says so once", async () => {
		// Not lucide's `circle-help` placeholder, which would sit in the rail unnoticed.
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		await loadSprite();

		const host = mount({ name: "not-an-icon" });
		mount({ name: "not-an-icon" });
		await nextTick();

		expect(host.querySelector("svg")).toBeNull();
		expect(host.textContent).toBe("");
		expect(warn).toHaveBeenCalledOnce();
	});

	it("says nothing while the sprite is still in flight", async () => {
		// Before it lands every name is legitimately absent.
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

		mount({ name: "users" });
		await nextTick();

		expect(warn).not.toHaveBeenCalled();
	});
});

describe("the reserved slot", () => {
	it("holds a row's indent open when there is nothing to draw", () => {
		const host = mount({ reserve: true });

		expect(host.querySelector("span")).not.toBeNull();
	});

	it("draws nothing at all without it", () => {
		const host = mount({});

		expect(host.querySelector("span")).toBeNull();
		expect(host.querySelector("svg")).toBeNull();
	});
});
