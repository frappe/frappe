// The one place a doctype URL's shape lives: a hand-built one is wrong under a modular
// prefix, and `TestNoHandBuiltDoctypeUrls` fails it. Every route stays inside the prefix.

import type { RouteLocationRaw, Router } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";

export type Shell = { boot: Boot; addresses: Addresses; router: Router };

// A slot, not a module-scope router: empty until `main.ts` fills it after boot.
let shell: Shell | null = null;

export function registerShell(context: Shell) {
	shell = context;
}

function current(): Shell {
	if (!shell)
		throw new Error("routeFor was called before the shell was mounted");
	return shell;
}

/** Does the app serving this prefix put the module in the address? */
export function isModular(boot: Boot): boolean {
	const prefix = boot.shell_base.split("/").filter(Boolean).pop();
	return Boolean(prefix && boot.prefixes?.[prefix]?.modular);
}

export type RouteOptions = {
	/** A saved view id, `/<doctype>/view/<viewName>`. Never a view type. */
	view?: string;
	/** Context, not identity: `?view=`, `?layout=` and friends. */
	query?: Record<string, string>;
};

/**
 * The route for a doctype's list, one of its saved views, or one record.
 *
 *   routeFor('CRM Deal')                          -> /crm-deal
 *   routeFor('CRM Deal', 'CRM-DEAL-01')           -> /crm-deal/CRM-DEAL-01
 *   routeFor('CRM Deal', null, { view: 'open' })  -> /crm-deal/view/open
 *
 * Under a modular prefix each is one segment deeper, with the doctype's own module.
 */
export function routeFor(
	doctype: string,
	name?: string | null,
	options: RouteOptions = {}
): RouteLocationRaw {
	const { boot, addresses } = current();
	const address = addresses.addressOf(doctype);

	if (!address) {
		// A guessed slug would reach not-found one hop later, with the reason lost.
		throw new Error(`routeFor: no address for doctype '${doctype}'`);
	}

	const [slug, module] = address;
	const params: Record<string, string> = { doctype: slug };
	if (isModular(boot)) {
		if (!module)
			throw new Error(
				`routeFor: '${doctype}' has no module under a modular prefix`
			);
		params.module = module;
	}

	if (name)
		return {
			name: "record",
			params: { ...params, name },
			query: options.query,
		};
	if (options.view) {
		return {
			name: "saved-view",
			params: { ...params, viewName: options.view },
			query: options.query,
		};
	}
	return { name: "list", params, query: options.query };
}

/** The route for a module's landing page. Modular prefixes only. */
export function routeForModule(moduleSlug: string): RouteLocationRaw {
	return { name: "module", params: { module: moduleSlug } };
}

/**
 * The same address as an href, for a `window.location` assignment or a plain `<a>`.
 */
export function urlFor(
	doctype: string,
	name?: string | null,
	options: RouteOptions = {}
): string {
	return current().router.resolve(routeFor(doctype, name, options)).href;
}
