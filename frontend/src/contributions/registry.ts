// THE SEAM. Everything the charter rests on passes through this file.
//
// It is deliberately tiny, and its size is the argument: the framework's side of the
// contribution contract is an index over a generated module. All the machinery lives
// in plugin/contributions.js, at build time, where it costs nothing at runtime.

import contributions from 'virtual:frappe/contributions'
import { registerRecordPage, withRegisteringSource } from '@/recordPage'
import type { ItemRenderer } from '@/navigation/types'
import type { DoctypeContribution, ListHandlers, PageContribution } from './types'

export const pages: PageContribution[] = contributions.pages

/** Item kind -> renderer, filled by `registerContributions` in the site's app order. */
export const itemRenderers: Record<string, ItemRenderer> = {}

/** List customizations, indexed by doctype. No registrar exists for these in
 *  the record-page engine yet, so the shell's own index holds them. */
const listHandlers = new Map<string, { app: string; handlers: ListHandlers }[]>()

export function listHandlersFor(doctype: string) {
  return listHandlers.get(doctype) ?? []
}

/**
 * Run order, per doctype: the doctype's OWNING app first, then every other app in the
 * site's `app_order` (#42113).
 *
 * Ownership needs no registry lookup here, because it is structural. A file at
 * `<module>/doctype/<x>/frontend/` is colocated in the owner's own tree, so it IS the
 * owner's; a file at `<module>/custom/<x>/` is by construction somebody else's. The
 * arrow rule 1 actually wanted was "baseline first, more-specific intent last", not
 * "framework first" -- and this is that, derived rather than declared.
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
 * Registration runs before the router's first resolution (see main.ts).
 *
 * App identity comes from the generated module, NOT from a path inspected at runtime
 * -- which is the whole reason the plugin synthesises rather than globs: a raw
 * `import.meta.glob` loses the app (#42068).
 */
export async function registerContributions(appOrder: string[]) {
  registerItemTypes(appOrder)

  const byDoctype = new Map<string, DoctypeContribution[]>()
  for (const contribution of contributions.doctypes) {
    const own = byDoctype.get(contribution.doctype) ?? []
    own.push(contribution)
    byDoctype.set(contribution.doctype, own)
  }

  // Doctype by doctype, because the ordering is per doctype rather than one global
  // sequence -- an app can be the owner of one and a foreigner to the next.
  for (const [doctype, all] of byDoctype) {
    for (const contribution of ordered(all, appOrder, (c) => c.kind === 'custom')) {
      if (contribution.kind === 'list') {
        const own = listHandlers.get(doctype) ?? []
        own.push({ app: contribution.app, handlers: contribution.handlers })
        listHandlers.set(doctype, own)
        continue
      }

      // Tagged with the contributing app, so a later `unregisterSource` can drop
      // exactly one app's handlers.
      await withRegisteringSource(contribution.app, async () =>
        registerRecordPage(doctype, contribution.handlers),
      )
    }
  }
}

/**
 * One renderer per item kind, and the FIRST app in the site's order wins.
 *
 * Two apps claiming one type name is a conflict rather than an override: the type record
 * itself is one row that one app ships, so a second renderer for it is aimed at somebody
 * else's kind. Last-wins is what #42228 rejected in `override_doctype_class`, whose
 * `[-1]` means the winner is decided by install order and nothing says so; first-wins
 * plus a line naming both apps is the same determinism with the collision visible.
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
