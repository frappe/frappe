// Contributed pages, from the virtual module the vite plugin synthesised at build time.

import type { Addresses } from '@/addresses'
import { pages } from '@/contributions/registry'
import type { PageContribution } from '@/contributions/types'

export function contributedRoutes(app: string | null, modular: boolean, addresses: Addresses) {
  if (!app) return []

  // Only the declaring app's pages: the same core-plus-declarer rule as boot.
  const own = pages.filter((page) => page.app === app)
  const shared = sharedSlugs(own)
  return own
    .filter((page) => !shared.has(page.slug) && !heldBySite(page, modular, addresses))
    .map((page) => ({
      path: `/${page.slug}`,
      name: `page:${page.app}:${page.slug}`,
      component: page.component,
      meta: { title: page.title },
    }))
}

/** Slugs more than one of an app's pages use; no order between them means anything. */
function sharedSlugs(own: PageContribution[]) {
  const seen = new Set<string>()
  const shared = new Set<string>()
  for (const { slug } of own) {
    if (seen.has(slug)) shared.add(slug)
    else seen.add(slug)
  }

  for (const slug of shared) {
    console.error(
      `[frappe] '${own[0].app}' ships more than one page named '${slug}'; all of them are dropped.`,
    )
  }
  return shared
}

/** A doctype on a flat prefix, or a module on a modular one, keeps the segment a page wants. */
function heldBySite(page: PageContribution, modular: boolean, addresses: Addresses) {
  const holder = modular
    ? addresses.hasModule(page.slug) && `module '${addresses.moduleName(page.slug)}'`
    : addresses.doctypeOf(page.slug) && `doctype '${addresses.doctypeOf(page.slug)}'`
  if (!holder) return false

  console.error(
    `[frappe] the page '${page.slug}' of '${page.app}' is dropped: the ${holder} ` +
      `already has the address /${page.slug}.`,
  )
  return true
}
