// Contributed pages, from the virtual module the vite plugin synthesised at build time.

import { pages } from '@/contributions/registry'

export function contributedRoutes(app: string | null) {
  if (!app) return []

  // Only the declaring app's pages: the same core-plus-declarer rule as boot.
  return pages
    .filter((page) => page.app === app)
    .map((page) => ({
      path: `/${page.slug}`,
      name: `page:${page.app}:${page.slug}`,
      component: page.component,
      meta: { title: page.title },
    }))
}
