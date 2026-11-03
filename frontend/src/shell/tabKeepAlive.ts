// While a standing window asks to keep the tab alive, nothing the shell does unloads this document, except logout.
import { toast } from "frappe-ui";
import { computed, onScopeDispose, watch } from "vue";
import { __ } from "@/i18n";
import type { StandingWindow } from "./standingWindows";

const THIS_TAB = new Set(["", "_self", "_top", "_parent"]);

let kept = false;

/** Loads `href` as another document: in a new tab while a standing window keeps this one alive. */
export function loadDocument(href: string) {
	if (!kept) return window.location.assign(href);
	// `noopener` makes `window.open` return null even for a tab that opened, so the opener is cut after.
	const tab = window.open(href, "_blank");
	if (tab) tab.opener = null;
	else offerTab(href);
}

/** Stops the unload prompt for a document the shell is about to leave on purpose, such as logout. */
export function allowUnload() {
	window.removeEventListener("beforeunload", askBeforeUnload);
}

// The browser blocks a tab opened after an awaited step; a click on the toast is a new gesture.
function offerTab(href: string) {
	toast(__("Your browser blocked the new tab"), {
		id: "blocked-new-tab",
		duration: Infinity,
		action: { label: __("Open"), onClick: () => window.open(href, "_blank", "noopener") },
	});
}

/** Holds the tab for as long as any of `windows` has keep-alive on. */
export function useTabKeepAlive(windows: () => readonly StandingWindow[]) {
	const alive = computed(() => windows().some((entry) => entry.keepAlive));
	const stop = watch(alive, (on) => (on ? hold() : release()), { immediate: true });
	onScopeDispose(() => {
		stop();
		release();
	});
}

function hold() {
	kept = true;
	document.addEventListener("click", openInNewTab);
	window.addEventListener("beforeunload", askBeforeUnload);
}

function release() {
	kept = false;
	document.removeEventListener("click", openInNewTab);
	window.removeEventListener("beforeunload", askBeforeUnload);
}

function askBeforeUnload(event: BeforeUnloadEvent) {
	event.preventDefault();
	event.returnValue = "";
}

// Runs after the router's own handler, which has prevented the default for a route it moves.
function openInNewTab(event: MouseEvent) {
	const plain = event.button === 0 && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey);
	const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
	if (event.defaultPrevented || !plain || !(link instanceof HTMLAnchorElement)) return;
	if (!THIS_TAB.has(link.target) || link.hasAttribute("download")) return;
	const url = new URL(link.href);
	const moves = /^https?:$/.test(url.protocol);
	const sameDocument = url.origin === location.origin && url.pathname + url.search === location.pathname + location.search;
	if (!moves || sameDocument) return;
	event.preventDefault();
	window.open(url.href, "_blank", "noopener");
}
