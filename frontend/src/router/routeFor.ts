// THE ONE SANCTIONED WAY TO BUILD A DOCTYPE URL.
//
// Two things made this necessary, and neither was true when the shell was written.
// The prefix became a lens, so a doctype is addressable under every prefix (#42210);
// and an app may declare `app_modular`, so the address gained a module segment
// (#42211). A hand-built `/${slug}/${name}` is now WRONG under a modular prefix, and
// wrong in the worst way -- it resolves, to the module route, and shows a page that
// is not the record. A 404, not a type error.
//
// So the shape must live in exactly one place. `routeFor` is that place, and the rule
// is enforced rather than documented: `TestNoHandBuiltDoctypeUrls` in
// `frappe/tests/test_shell.py` scans this repo's frontend source AND every installed
// app's contributed files, and fails naming file and line. The allowlist there is
// short, explicit and carries a reason each.
//
// What it does NOT do is cross a prefix. Following a link never leaves the prefix you
// are standing in -- that is what the lens bought -- so every route this builds is
// prefix-relative and the router's base supplies the rest. Crossing a prefix is a
// full document load (#42102) and wants `urlFor`.

import type { RouteLocationRaw, Router } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";

export type Shell = { boot: Boot; addresses: Addresses; router: Router };

// Module-scope, and worth being explicit about why that is allowed when #42072 forbids
// a module-scope ROUTER: this is not one. It is a slot, empty until `main.ts` fills it
// with the single shell this document owns, after boot has said what the base is. One
// document, one prefix, one shell -- the invariant the whole map rests on.
let shell: Shell | null = null;

export function registerShell(context: Shell) {
  shell = context;
}

function current(): Shell {
  if (!shell)
    throw new Error("routeFor was called before the shell was mounted");
  return shell;
}

/** Does the app serving THIS prefix put the module in the address? */
export function isModular(boot: Boot): boolean {
  const prefix = boot.shell_base.split("/").filter(Boolean).pop();
  return Boolean(prefix && boot.prefixes?.[prefix]?.modular);
}

export type RouteOptions = {
  /** A saved view id -- `/<doctype>/view/<viewName>`. Never a view *type* (#42068). */
  view?: string;
  /** Context, not identity. `?view=`, `?layout=` and friends live here (#42068). */
  query?: Record<string, string>;
};

/**
 * The route for a doctype's list, one of its saved views, or one record.
 *
 *   routeFor('CRM Deal')                          -> /crm-deal
 *   routeFor('CRM Deal', 'CRM-DEAL-01')           -> /crm-deal/CRM-DEAL-01
 *   routeFor('CRM Deal', null, { view: 'open' })  -> /crm-deal/view/open
 *
 * and under a modular prefix, each of those one segment deeper, with the doctype's
 * OWN module -- foreign doctypes included, because the shape is fixed per app.
 */
export function routeFor(
  doctype: string,
  name?: string | null,
  options: RouteOptions = {}
): RouteLocationRaw {
  const { boot, addresses } = current();
  const address = addresses.addressOf(doctype);

  if (!address) {
    // A doctype the table has never heard of cannot be addressed, and guessing a slug
    // would produce a URL that resolves to the shell's not-found anyway -- one hop
    // later and with the reason lost. Say it here, where the caller is.
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

/** The route for a module's landing page. Modular prefixes only (#42211 §6). */
export function routeForModule(moduleSlug: string): RouteLocationRaw {
  return { name: "module", params: { module: moduleSlug } };
}

/**
 * The same address as an href, for the two cases a route object cannot serve: a
 * `window.location` assignment from a contributed script, and a plain `<a>`.
 */
export function urlFor(
  doctype: string,
  name?: string | null,
  options: RouteOptions = {}
): string {
  return current().router.resolve(routeFor(doctype, name, options)).href;
}
