// The sprite loader: one fetch per document, and what a failed one costs.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	hasSymbol,
	isEmoji,
	loadSprite,
	reportMissingIcon,
	resetSprite,
	spriteLoaded,
	symbolId,
} from "../sprite";

const SPRITE =
	'<svg id="frappe-symbols" style="display:none">' +
	'<symbol id="icon-users" viewBox="0 0 24 24"><circle cx="9" cy="7" r="4"/></symbol>' +
	'<symbol id="icon-handshake" viewBox="0 0 24 24"><path d="M1 1"/></symbol>' +
	"</svg>";

function stubFetch(body = SPRITE, ok = true) {
	const fetch = vi.fn().mockResolvedValue({
		ok,
		status: ok ? 200 : 404,
		statusText: ok ? "OK" : "Not Found",
		text: () => Promise.resolve(body),
	});
	vi.stubGlobal("fetch", fetch);
	return fetch;
}

beforeEach(() => {
	document.body.innerHTML = "";
	resetSprite();
});

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe("loadSprite", () => {
	it("fetches once however many callers ask", async () => {
		// A sprite fetched per row would be 450 KB times the rail.
		const fetch = stubFetch();

		await Promise.all([loadSprite(), loadSprite(), loadSprite()]);

		expect(fetch).toHaveBeenCalledTimes(1);
		expect(fetch.mock.calls[0][0]).toBe("/assets/frappe/icons/lucide/icons.svg");
	});

	it("puts the symbols in the document and flips spriteLoaded", async () => {
		stubFetch();
		expect(spriteLoaded.value).toBe(false);

		await loadSprite();

		expect(spriteLoaded.value).toBe(true);
		expect(document.getElementById("frappe-icon-sprite")).not.toBeNull();
		expect(hasSymbol("users")).toBe(true);
		expect(hasSymbol("not-an-icon")).toBe(false);
	});

	it("does not answer to `lucide-sprite`", async () => {
		// That id belongs to frappe-ui's sprite, whose symbols carry bare ids, and
		// `recordPage/iconClasses.ts` reads it.
		stubFetch();

		await loadSprite();

		expect(document.getElementById("lucide-sprite")).toBeNull();
	});

	it("degrades when the sprite cannot be fetched", async () => {
		// The rows keep their labels and their destinations.
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		stubFetch("", false);

		await loadSprite();

		expect(spriteLoaded.value).toBe(false);
		expect(hasSymbol("users")).toBe(false);
		expect(error).toHaveBeenCalledOnce();
	});
});

describe("hasSymbol", () => {
	it("is false before the sprite lands", () => {
		expect(hasSymbol("users")).toBe(false);
	});

	it("does not find a symbol outside the sprite", async () => {
		// `icon-users` is a bare word an app could put on an element of its own.
		stubFetch();
		await loadSprite();
		const stray = document.createElement("div");
		stray.id = "icon-stray";
		document.body.appendChild(stray);

		expect(hasSymbol("stray")).toBe(false);
	});
});

describe("isEmoji", () => {
	it("agrees with frappe.utils.is_emoji about what the Icon field stores", () => {
		// Both values come out of one picker, so one has to read the other's writing.
		expect(isEmoji("🚀")).toBe(true);
		expect(isEmoji("⚠️")).toBe(true);
		expect(isEmoji("users")).toBe(false);
		expect(isEmoji("contact-round")).toBe(false);
		expect(isEmoji("")).toBe(false);
	});
});

describe("symbolId", () => {
	it("uses the sprite's own spelling", () => {
		expect(symbolId("users")).toBe("icon-users");
	});
});

describe("reportMissingIcon", () => {
	it("says a name once, not once per row", async () => {
		// Every row of a sidebar can name the same missing icon.
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

		reportMissingIcon("nope");
		reportMissingIcon("nope");
		reportMissingIcon("also-nope");

		expect(warn).toHaveBeenCalledTimes(2);
	});
});
