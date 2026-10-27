// The icon bridge: a script may name any lucide icon, and the class is
// generated from the geometry the host's icon source hands back.
import { beforeEach, describe, expect, it, vi } from "vitest";

const STYLE_ID = "record-page-icon-classes";

// A host source over a few symbols; a name it lacks resolves to `null`, as the sprite's does.
function sourceOver(...names: string[]) {
	return vi.fn((name: string) =>
		Promise.resolve(names.includes(name) ? `<path d="M4 4h16" />` : null),
	);
}

function rules() {
	return document.getElementById(STYLE_ID)?.textContent ?? "";
}

async function settled() {
	await new Promise((resolve) => setTimeout(resolve, 0));
}

// The bridged-icon cache is module state, so each test needs a fresh module.
async function freshModule(source?: ReturnType<typeof sourceOver>) {
	vi.resetModules();
	const module = await import("../iconClasses");
	module.setIconSource(source ?? null);
	return module;
}

beforeEach(() => {
	document.head.innerHTML = "";
	document.body.innerHTML = "";
});

describe("ensureIconClass", () => {
	it("generates a masked rule from the symbol the source hands back", async () => {
		const { ensureIconClass } = await freshModule(sourceOver("flag"));

		ensureIconClass("lucide-flag");
		await settled();

		expect(rules()).toContain(".lucide-flag{");
		expect(rules()).toContain('mask-image:url("data:image/svg+xml;utf8,');
		// The symbol's geometry, wrapped in a stroke-normalized svg.
		expect(decodeURIComponent(rules())).toContain('<path d="M4 4h16" />');
		expect(decodeURIComponent(rules())).toContain('stroke-width="1.5"');
	});

	it("asks the source for the bare name, without the class prefix", async () => {
		const source = sourceOver("flag");
		const { ensureIconClass } = await freshModule(source);

		ensureIconClass("lucide-flag");

		expect(source).toHaveBeenCalledWith("flag");
	});

	it("emits a rule once however often an icon is named", async () => {
		const source = sourceOver("flag");
		const { ensureIconClass } = await freshModule(source);

		ensureIconClass("lucide-flag");
		ensureIconClass("lucide-flag");
		await settled();

		expect(source).toHaveBeenCalledOnce();
		expect(rules().match(/\.lucide-flag\{/g)).toHaveLength(1);
	});

	it("draws an icon named before the sprite lands, once it does", async () => {
		let land!: (geometry: string) => void;
		const source = vi.fn(() => new Promise<string | null>((resolve) => (land = resolve)));
		const { ensureIconClass } = await freshModule(source);

		ensureIconClass("lucide-flag");
		await settled();
		expect(document.getElementById(STYLE_ID)).toBeNull();

		land(`<path d="M4 4h16" />`);
		await settled();
		expect(rules()).toContain(".lucide-flag{");
	});

	it("ignores icons the host already ships classes for", async () => {
		const source = sourceOver("flag");
		const { ensureIconClass } = await freshModule(source);

		ensureIconClass(undefined);
		ensureIconClass("space-dashboard"); // a non-lucide pack
		await settled();

		expect(source).not.toHaveBeenCalled();
		expect(document.getElementById(STYLE_ID)).toBeNull();
	});

	it("warns and emits nothing for a name the source does not carry", async () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const { ensureIconClass } = await freshModule(sourceOver("flag"));

		ensureIconClass("lucide-not-an-icon");
		ensureIconClass("lucide-not-an-icon");
		await settled();

		expect(document.getElementById(STYLE_ID)).toBeNull();
		expect(warn).toHaveBeenCalledOnce();
		expect(warn.mock.calls[0][0]).toContain("lucide-not-an-icon");
		warn.mockRestore();
	});

	it("warns once for a host with no icon source, not once per icon", async () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const { ensureIconClass } = await freshModule();

		ensureIconClass("lucide-flag");
		ensureIconClass("lucide-scroll-text");
		await settled();

		expect(document.getElementById(STYLE_ID)).toBeNull();
		expect(warn).toHaveBeenCalledOnce();
		warn.mockRestore();
	});

	// Prepended, so a `size-4` at the call site still beats the rule's own `width: 1em`.
	it("puts its style ahead of the app's stylesheets", async () => {
		document.head.appendChild(document.createElement("link"));
		const { ensureIconClass } = await freshModule(sourceOver("flag"));

		ensureIconClass("lucide-flag");
		await settled();

		expect(document.head.firstElementChild?.id).toBe(STYLE_ID);
	});
});

describe("ensureIconClass with a failing source", () => {
	it("warns with the engine's prefix instead of leaving a rejection unhandled", async () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const { ensureIconClass } = await freshModule(vi.fn(() => Promise.reject(new Error("down"))));

		ensureIconClass("lucide-flag");
		await settled();

		expect(document.getElementById(STYLE_ID)).toBeNull();
		expect(warn).toHaveBeenCalledOnce();
		expect(warn.mock.calls[0][0]).toContain("[record-page]");
		warn.mockRestore();
	});
});

describe("ensureIcons", () => {
	it("bridges an item's own icon and a tab's create-action icon", async () => {
		const { ensureIcons } = await freshModule(sourceOver("scroll-text", "plus"));

		ensureIcons({
			name: "audit-log",
			icon: "lucide-scroll-text",
			create: { label: "New", icon: "lucide-plus", run: () => {} },
		});
		await settled();

		expect(rules()).toContain(".lucide-scroll-text{");
		expect(rules()).toContain(".lucide-plus{");
	});
});
