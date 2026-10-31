// The contribution seam: an index over the module `plugin/contributions.js` generates at build time.

import contributions from 'virtual:frappe/contributions'
import { addFileScript, addPageFile } from '@/recordPage'
import type { ItemRenderer } from '@/navigation/types'
import type {
  ActsContribution,
  DoctypeContribution,
  ListHandlers,
  PageContribution,
  ReplacementContribution,
  ShellHookContribution,
  StandardPages,
} from './types'

export const pages: PageContribution[] = contributions.pages

/** Item kind -> renderer, filled by `registerContributions` in the site's app order. */
export const itemRenderers: Record<string, ItemRenderer> = {}

/** List customizations by doctype; the record-page engine has no registrar for these. */
const listHandlers = new Map<string, { app: string; handlers: ListHandlers }[]>()

export function listHandlersFor(doctype: string) {
  return listHandlers.get(doctype) ?? []
}

let standard: StandardPages | null = null

/** The default page of every address; registered before the router is built. */
export function registerStandardPages(pages: StandardPages) {
  standard = pages
}

export function standardPage<Key extends keyof StandardPages>(key: Key) {
  if (!standard) throw new Error('[frappe] a standard page is read before it is registered.')
  return standard[key]
}

/** Page key and doctype -> the active apps' replacements in run order; see `registerContributions`. */
const claims = new Map<string, ReplacementContribution[]>()

/**
 * The page that replaces a doctype's page in `app`: an entry naming `app` beats every entry
 * naming no apps, and among equals the last in run order wins.
 */
export function replacementFor(
  doctype: string,
  key: ReplacementContribution['key'],
  app: string | null,
) {
  return contendersIn(claims.get(`${key}:${doctype}`) ?? [], app).at(-1)
}

/** Every page that wins in `app`, for checks that need the address table. */
export function declaredReplacements(app: string | null) {
  return [...claims.values()].flatMap((all) => contendersIn(all, app).slice(-1))
}

/** One error per page that more than one entry of equal standing replaces in `app`. */
export function reportReplacementClashes(app: string) {
  for (const all of claims.values()) {
    const contenders = contendersIn(all, app)
    if (contenders.length < 2) continue

    const winner = contenders[contenders.length - 1]
    const losers = contenders.slice(0, -1).map((c) => `'${c.app}'`)
    console.error(
      `[frappe] ${contenders.length} apps replace the ${winner.key} page of '${winner.doctype}'` +
        ` in '${app}': '${winner.app}' is used and ${losers.join(', ')} ignored.`,
    )
  }
}

/** The component a settings block names, or nothing, with a warning, when no such file ships. */
export function settingsComponentFor(app: string, name: string) {
  const found = contributions.settings.find((entry) => entry.app === app && entry.name === name)
  if (!found) {
    console.warn(
      `[frappe] settings block dropped: the build holds no settings component '${name}' from ${app}.`,
    )
  }
  return found?.component
}

/** Each active app's `acts.js`, in the site's app order; filled by `registerContributions`. */
export const actsFiles: ActsContribution[] = []

/** Each active app's `shell.js`, in the site's app order; filled by `registerContributions`. */
export const shellHookFiles: ShellHookContribution[] = []

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
export function registerContributions(appOrder: string[]) {
  registerItemTypes(appOrder)
  registerReplacements(appOrder)
  registerPageScripts(appOrder)
  registerActs(appOrder)
  registerShellHooks(appOrder)

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

      addFileScript(doctype, { app: contribution.app, handlers: contribution.handlers })
    }
  }
}

/** Only an app the site has active adds acts, in the site's order. */
function registerActs(appOrder: string[]) {
  const active = contributions.acts.filter((contribution) => appOrder.includes(contribution.app))
  actsFiles.length = 0
  actsFiles.push(...ordered(active, appOrder))
}

function registerShellHooks(appOrder: string[]) {
  const active = (contributions.shellHooks ?? []).filter((c) => appOrder.includes(c.app))
  shellHookFiles.length = 0
  shellHookFiles.push(...ordered(active, appOrder))
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

/** Per doctype and page key, the active apps' replacements in run order. */
function registerReplacements(appOrder: string[]) {
  for (const contribution of ordered(contributions.replacements, appOrder, (c) => c.foreign)) {
    if (!appOrder.includes(contribution.app)) continue
    const slot = `${contribution.key}:${contribution.doctype}`
    claims.set(slot, [...(claims.get(slot) ?? []), contribution])
  }
}

/** Only an active app's handler files; each runs on its own app's page alone. */
function registerPageScripts(appOrder: string[]) {
  for (const { app, doctype, page, handlers } of contributions.pageScripts ?? []) {
    if (appOrder.includes(app)) addPageFile(app, doctype, page, handlers)
  }
}

function contendersIn(all: ReplacementContribution[], app: string | null) {
  const scoped = all.filter((c) => app !== null && c.apps?.includes(app))
  return scoped.length ? scoped : all.filter((c) => !c.apps)
}
