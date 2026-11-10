// An app's tab icon: the page ships the framework's, and the app's `brand` favicon replaces it.
import { beforeEach, describe, expect, it } from "vitest";
import { applyAppFavicon } from "@/shell/appFavicon";

const FRAMEWORK_ICON = "/assets/frappe/images/frappe-framework-logo.svg";

function tabIcon(): string | null {
	return document.querySelector('link[rel="icon"]')?.getAttribute("href") ?? null;
}

describe("applyAppFavicon", () => {
	beforeEach(() => {
		document.head.innerHTML = `<link rel="icon" href="${FRAMEWORK_ICON}" />`;
	});

	it("replaces the tab icon with the app's favicon", () => {
		applyAppFavicon("/files/acme-icon.png");

		expect(tabIcon()).toBe("/files/acme-icon.png");
	});

	it.each([null, undefined, ""])("keeps the framework's icon when the favicon is %s", (favicon) => {
		applyAppFavicon(favicon);

		expect(tabIcon()).toBe(FRAMEWORK_ICON);
	});
});
