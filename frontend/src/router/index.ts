// One router per document, based at `boot.shell_base`; every route path is prefix-relative.
// It is created after boot, never at module scope: the base comes out of boot.

import { createRouter, createWebHistory } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import {
	declaredReplacements,
	reportReplacementClashes,
	standardPage,
	viewRenderers,
} from "@/contributions/registry";
import { generatedRoutes, indexRoutes } from "./generated";
import { contributedRoutes } from "./contributed";
import { afterFramePaint } from "./mainPage";
import { canonicalAddress } from "@/navigation/canonical";
import { isModular } from "./routeFor";
import { landingOf } from "@/navigation/landing";
import { flushPendingRecordDialog } from "@/shell/recordDialog";
import { recordDialogAnswer } from "./recordDialogGuard";
import { clearSkip, consumeSkip } from "./skipDefault";
import NotFound from "@/shell/NotFound.vue";

const RECORD_ROUTES = new Set(["record", "standard-record"]);
const VIEW_ROUTES = new Set(["list", "standard-list", "saved-view"]);

// The static segment outranks `/:doctype/:name` and `/:module/:doctype`, so a
// DocType's record page moves to `/doctype/<name>/record`; the list keeps `/doctype`.
function doctypeEditorRoute() {
	return { path: "/doctype/:name", name: "doctype-editor", component: standardPage("doctypeEditor") };
}

export function createShellRouter(boot: Boot, addresses: Addresses) {
	const modular = isModular(boot);
	warnIgnoredListPages(addresses, boot.app);
	if (boot.app) reportReplacementClashes(boot.app);

	const router = createRouter({
		history: createWebHistory(boot.shell_base),
		routes: [
			...(boot.app ? [doctypeEditorRoute()] : []),
			// Contributed pages match before generated routes: `/deals` must beat `/:doctype`.
			...contributedRoutes(boot.app, modular, addresses),
			...(boot.app ? generatedRoutes(modular) : indexRoutes()),
			{
				path: "/:pathMatch(.*)*",
				name: "not-found",
				component: NotFound,
			},
		],
	});

	router.afterEach((to, _from, failure) => {
		clearSkip();
		flushPendingRecordDialog(to.fullPath, !!failure);
	});

	// Canonicalise the doctype segment to its slug, never away from it: the slug is the address.
	router.beforeResolve((to, from) => {
		// A record must not render under a module it does not belong to, nor a doctype under its name.
		const canonical = canonicalAddress(to, addresses);
		if (canonical) return canonical;

		if (modular && typeof to.params.module === "string" && to.params.module) {
			// Not a module and no flat address reads through it: a miss.
			if (!addresses.hasModule(to.params.module)) return miss(to);
		}

		// No `replace`: the bare address never enters history, and forcing one drops the entry before it.
		if (to.name === "home" || to.name === "module") {
			const moduleSlug = to.name === "module" ? String(to.params.module) : undefined;
			const landing = landingOf(boot, addresses, router, moduleSlug);
			return landing ? { path: landing.path, query: landing.query, hash: to.hash } : true;
		}

		const segment = to.params.doctype;
		if (typeof segment !== "string" || !segment) return true;
		const doctype = addresses.doctypeOf(segment);
		if (doctype) {
			// A single has no list to show: its list address is the document, as `routeFor` spells
			// it. The module segment is checked on the next pass, as for any record.
			if (addresses.isSingle(doctype) && !RECORD_ROUTES.has(String(to.name))) {
				// Named params only: a saved view's `key` has no slot on the record route.
				const params: Record<string, string> = { doctype: segment, name: doctype };
				if (typeof to.params.module === "string") params.module = to.params.module;
				return { name: "record", params, query: to.query, replace: true };
			}
			// A single's address is its document, and a submittable needs Submit and Cancel: never a dialog.
			const dialog = addresses.isSingle(doctype) || addresses.isSubmittable(doctype)
				? undefined
				: recordDialogAnswer(to, from, doctype, boot.app);
			if (dialog !== undefined) return dialog;

			// Like a landing: a query states its own list, and the bare address never enters history.
			// A query change on the list the person is already on is the page's own, never a new visit.
			const view = boot.default_views?.[doctype];
			if (view && to.name === "list" && !Object.keys(to.query).length && !consumeSkip(doctype) && from.path !== to.path)
				return { path: `${to.path.replace(/\/$/, "")}/view/${view}`, hash: to.hash };
			if (VIEW_ROUTES.has(String(to.name))) preloadRenderer(boot, String(to.params.key ?? "list"));
			return true;
		}

		// The shell owns the miss; otherwise `/:doctype` swallows every unknown path as an empty list.
		return miss(to);
	});

	return router;
}

/** A single has no list, so a list page declared for one never opens. */
function warnIgnoredListPages(addresses: Addresses, app: string | null) {
	for (const page of declaredReplacements(app)) {
		if (page.key !== "list" || !addresses.isSingle(page.doctype)) continue;
		console.warn(
			`[frappe] '${page.app}' replaces the list page of '${page.doctype}', a single with no ` +
				"list; the declaration is ignored."
		);
	}
}

function miss(to: { path: string }) {
	return {
		name: "not-found",
		params: { pathMatch: to.path.slice(1).split("/") },
		replace: true,
	};
}

/** Starts loading the renderer of the view type an address segment names, once the frame paints. */
function preloadRenderer(boot: Boot, segment: string) {
	const type = boot.view_types?.find((one) => one.name.toLowerCase() === segment)?.name;
	const load = type && viewRenderers[type];
	// After the paint: an import in the click's task holds it. The page reports a failed load.
	if (load) void afterFramePaint().then(load).catch(() => {});
}
