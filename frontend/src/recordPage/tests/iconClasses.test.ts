// The icon bridge: a script may name any lucide icon, and the class is
// generated from the sprite already in the page.
import { beforeEach, describe, expect, it, vi } from "vitest";

const STYLE_ID = "record-page-icon-classes";

function installSprite(...names: string[]) {
	const sprite = document.createElement("div");
	sprite.id = "lucide-sprite";
	sprite.innerHTML = names
		.map((name) => `<symbol id="${name}" viewBox="0 0 24 24"><path d="M4 4h16" /></symbol>`)
		.join("");
	document.body.prepend(sprite);
}

function rules() {
	return document.getElementById(STYLE_ID)?.textContent ?? "";
}

// The bridged-icon cache is module state, so each test needs a fresh module.
async function freshModule() {
	vi.resetModules();
	return await import("../iconClasses");
}

beforeEach(() => {
	document.head.innerHTML = "";
	document.body.innerHTML = "";
});

describe("ensureIconClass", () => {
	it("generates a masked rule from the sprite symbol", async () => {
		installSprite("flag");
		const { ensureIconClass } = await freshModule();

		ensureIconClass("lucide-flag");

		expect(rules()).toContain(".lucide-flag{");
		expect(rules()).toContain('mask-image:url("data:image/svg+xml;utf8,');
		// The symbol's geometry, wrapped in a stroke-normalized svg.
		expect(decodeURIComponent(rules())).toContain('<path d="M4 4h16">');
		expect(decodeURIComponent(rules())).toContain('stroke-width="1.5"');
	});

	it("emits a rule once however often an icon is named", async () => {
		installSprite("flag");
		const { ensureIconClass } = await freshModule();

		ensureIconClass("lucide-flag");
		ensureIconClass("lucide-flag");

		expect(rules().match(/\.lucide-flag\{/g)).toHaveLength(1);
	});

	it("ignores icons the host already ships classes for", async () => {
		installSprite("flag");
		const { ensureIconClass } = await freshModule();

		ensureIconClass(undefined);
		ensureIconClass("space-dashboard"); // a non-lucide pack

		expect(document.getElementById(STYLE_ID)).toBeNull();
	});

	it("warns and emits nothing for a name the sprite does not carry", async () => {
		installSprite("flag");
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const { ensureIconClass } = await freshModule();

		ensureIconClass("lucide-not-an-icon");

		expect(document.getElementById(STYLE_ID)).toBeNull();
		expect(warn).toHaveBeenCalledOnce();
		warn.mockRestore();
	});

	it("warns once for a missing sprite, not once per icon", async () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const { ensureIconClass } = await freshModule();

		ensureIconClass("lucide-flag");
		ensureIconClass("lucide-scroll-text");

		expect(warn).toHaveBeenCalledOnce();
		warn.mockRestore();
	});

	// Prepended, so a `size-4` at the call site still beats the rule's own `width: 1em`.
	it("puts its style ahead of the app's stylesheets", async () => {
		installSprite("flag");
		document.head.appendChild(document.createElement("link"));
		const { ensureIconClass } = await freshModule();

		ensureIconClass("lucide-flag");

		expect(document.head.firstElementChild?.id).toBe(STYLE_ID);
	});
});

describe("ensureIcons", () => {
	it("bridges an item's own icon and a tab's create-action icon", async () => {
		installSprite("scroll-text", "plus");
		const { ensureIcons } = await freshModule();

		ensureIcons({
			name: "audit-log",
			icon: "lucide-scroll-text",
			create: { label: "New", icon: "lucide-plus", run: () => {} },
		});

		expect(rules()).toContain(".lucide-scroll-text{");
		expect(rules()).toContain(".lucide-plus{");
	});
});
