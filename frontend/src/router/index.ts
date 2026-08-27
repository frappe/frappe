// HOW ONE ROUTER SERVES N PREFIXES.
//
// The router's base is `boot.shell_base`, set at runtime, and every route path in the
// system is prefix-relative. There is exactly one prefix live in a given page load —
// the one the request came in at — so the router never sees two.
//
// The rejected alternative was `base: '/'` with prefix-carrying route paths. Its only
// advantage is cross-prefix `router.push`, and that is precisely what boot being
// prefix-scoped already makes impossible without a re-fetch: arriving at `/apps/desk`
// carrying `/apps/crm`'s boot gives you the wrong app's contributed keys with nothing
// to notice it. So it pays a real cost — the prefix leaves hooks.py and enters JS —
// to enable something already known not to be free (#42072).
//
// The consequence that shapes main.ts: the router CANNOT be a module-scope singleton.

import { createRouter, createWebHistory } from 'vue-router'
import type { Boot } from '@/boot'
import { generatedRoutes } from './generated'
import { contributedRoutes } from './contributed'

export function createShellRouter(boot: Boot) {
  const router = createRouter({
    // The prefix, asked for at runtime. The one line this file argues about.
    history: createWebHistory(boot.shell_base),
    routes: [
      // Order matters and is not arbitrary: contributed pages match BEFORE generated
      // doctype routes, because `/deals` must beat `/:doctype`. They share one flat
      // namespace (#42068).
      //
      // #42068 said an install-time check would guard that namespace. It is NOT built
      // -- neither `install.py` nor the manifest validates slugs -- so today a page
      // file named `crm-deal.js` silently shadows the CRM Deal list, and two pages with
      // the same slug in different modules resolve last-wins. See this ticket's
      // "deliberately not built".
      ...contributedRoutes(boot.app),
      ...generatedRoutes(),
      { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/shell/NotFound.vue') },
    ],
  })

  // Canonicalise the doctype segment TO its slug -- never away from it. The slug is
  // the address, so a pasted `/apps/crm/CRM Deal/CRM-DEAL-01` is redirected to
  // `/apps/crm/crm-deal/CRM-DEAL-01` and not the other way about. Rewriting the
  // param to the real doctype name would put `CRM Deal` in the URL bar, which is the
  // opposite of "path is identity" (#42068).
  //
  // Synchronous, because the table came down with boot; CRM's frontend2 needs a
  // server round-trip in `beforeResolve` today.
  router.beforeResolve((to) => {
    const segment = to.params.doctype
    if (typeof segment !== 'string' || !segment) return true
    // `Object.hasOwn`, not a bare bracket read: a plain object inherits from
    // Object.prototype, so `/apps/crm/constructor` and `/apps/crm/toString` would
    // otherwise pass the 'is this a doctype' guard and hand the page a function.
    if (Object.hasOwn(boot.doctype_slugs, segment)) return true

    const canonical = slugOfDoctype(boot, segment)
    if (canonical) return { ...to, params: { ...to.params, doctype: canonical }, replace: true }

    // A segment that is neither a slug nor a doctype is a route miss, and the SHELL
    // owns that state -- an app cannot brand its own 404 (#42072). Without this the
    // `/:doctype` route swallows every unknown path and shows an empty list, which
    // reads as "this doctype has no records" rather than "there is no such thing".
    // The document was already served at 200; the miss is the router's to report.
    return { name: 'not-found', params: { pathMatch: to.path.slice(1).split('/') }, replace: true }
  })

  return router
}

function slugOfDoctype(boot: Boot, doctype: string) {
  const match = Object.entries(boot.doctype_slugs).find(
    ([, name]) => name.toLowerCase() === doctype.toLowerCase(),
  )
  return match?.[0]
}

/** The real doctype behind a URL segment, or null if this prefix does not serve one. */
export function resolveDoctype(boot: Boot, segment: string): string | null {
  if (!Object.hasOwn(boot.doctype_slugs, segment)) return null
  return boot.doctype_slugs[segment]
}
