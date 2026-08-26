// Contributed pages, from the synthesised virtual module.
//
// The file is short because the plugin did the work at build time. There is no hook
// to read, no boot key to walk and no install order to respect -- the contributions
// are already in this bundle.

import { pages } from '@/contributions/registry'

export function contributedRoutes(app: string | null) {
  if (!app) return []

  // Only the declaring app's pages. A ten-app bench does not put ten apps' pages in
  // one prefix's route table -- the same core-plus-declarer rule as boot (#42070).
  return pages
    .filter((page) => page.app === app)
    .map((page) => ({
      path: `/${page.slug}`,
      name: `page:${page.app}:${page.slug}`,
      component: page.component,
      meta: { title: page.title },
    }))
}
