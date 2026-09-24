// The contribution seam: an index over the module `plugin/contributions.js` generates at build time.

import contributions from 'virtual:frappe/contributions'
import { registerRecordPage, withRegisteringSource } from '@/recordPage'
import type { ItemRenderer } from '@/navigation/types'
import type {
  DoctypeContribution,
  ListHandlers,
  PageContribution,
  ReplacementContribution,
} from './types'

export const pages: PageContribution[] = contributions.pages

/** Item kind -> renderer, filled by `registerContributions` in the site's app order. */
export const itemRenderers: Record<string, ItemRenderer> = {}

/** List customizations by doctype; the record-page engine has no registrar for these. */
const listHandlers = new Map<string, { app: string; handlers: ListHandlers }[]>()

export function listHandlersFor(doctype: string) {
  return listHandlers.get(doctype) ?? []
}

/** Page key and doctype -> the one page that replaces it, filled by `registerContributions`. */
const replacements = new Map<string, ReplacementContribution>()

export function replacementFor(doctype: string, key: ReplacementContribution['key']) {
  return replacements.get(`${key}:${doctype}`)
}

/** Every winning replacement, for checks that need the address table. */
export function declaredReplacements() {
  return [...replacements.values()]
}

/**
 * Run order per doctype: the owning app first, then the site's `app_order`. Ownership is
 * structural: a file under `custom/` is somebody else's doctype.
 */
function ordered<T extends { app: string }>(
  all: T[],
  appOrder: string[],
  isForeign: (c: T) => boolean = () => false,
) {
  const rank = (c: T) => {
    const foreign = isForeign(c) ? 1 : 0
    const position = appOrder.indexOf(c.app)
    return [foreign, position < 0 ? appOrder.length : position] as const
  }

  return [...all].sort((a, b) => {
    const [aForeign, aPos] = rank(a)
    const [bForeign, bPos] = rank(b)
    return aForeign - bForeign || aPos - bPos
  })
}

/**
 * Runs before the router's first resolution. App identity comes from the generated
 * module, never from a path inspected at runtime.
 */
export async function registerContributions(appOrder: string[]) {
  registerItemTypes(appOrder)
  registerReplacements(appOrder)

  const byDoctype = new Map<string, DoctypeContribution[]>()
  for (const contribution of contributions.doctypes) {
    const own = byDoctype.get(contribution.doctype) ?? []
    own.push(contribution)
    byDoctype.set(contribution.doctype, own)
  }

  // Ordering is per doctype: an app can own one and be foreign to the next.
  for (const [doctype, all] of byDoctype) {
    for (const contribution of ordered(all, appOrder, (c) => c.kind === 'custom')) {
      if (contribution.kind === 'list') {
        const own = listHandlers.get(doctype) ?? []
        own.push({ app: contribution.app, handlers: contribution.handlers })
        listHandlers.set(doctype, own)
        continue
      }

      // Tagged with the app, so `unregisterSource` can drop exactly one app's handlers.
      await withRegisteringSource(contribution.app, async () =>
        registerRecordPage(doctype, contribution.handlers),
      )
    }
  }
}

/**
 * One renderer per kind; the first app in the site's order wins and the collision is logged.
 */
function registerItemTypes(appOrder: string[]) {
  const owner: Record<string, string> = {}

  for (const contribution of ordered(contributions.itemTypes, appOrder)) {
    const claimed = owner[contribution.type]
    if (claimed) {
      console.error(
        `[frappe] two apps ship a renderer for navigation item type '${contribution.type}': ` +
          `'${claimed}' is used and '${contribution.app}' is ignored.`,
      )
      continue
    }

    owner[contribution.type] = contribution.app
    itemRenderers[contribution.type] = contribution.renderer
  }
}

/**
 * Per doctype and page key the last active app in run order wins, and a contested key is logged.
 */
function registerReplacements(appOrder: string[]) {
  const claims = new Map<string, ReplacementContribution[]>()
  for (const contribution of ordered(contributions.replacements, appOrder, (c) => c.foreign)) {
    if (!appOrder.includes(contribution.app)) continue
    const slot = `${contribution.key}:${contribution.doctype}`
    claims.set(slot, [...(claims.get(slot) ?? []), contribution])
  }

  for (const [slot, all] of claims) {
    const winner = all[all.length - 1]
    replacements.set(slot, winner)
    if (all.length < 2) continue

    const losers = all.slice(0, -1).map((c) => `'${c.app}'`)
    console.error(
      `[frappe] ${all.length} apps replace the ${winner.key} page of '${winner.doctype}': ` +
        `'${winner.app}' is used and ${losers.join(', ')} ignored.`,
    )
  }
}
