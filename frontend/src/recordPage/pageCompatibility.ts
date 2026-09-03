// What happens to a script that reaches for a removed `page` name: a tombstone
// throws naming the replacement, a gone name warns once on read.
//
// Narrowed to the list, never any unknown key: `if (page.dialog.prompt)` is the
// feature detection authors are told to write, and it must stay silent.
import { runningSource } from "./context";
import { toastScriptError } from "./pageScripts";
import { reportCustomizationError } from "./reportError";

export interface Removal {
  /** Dotted path from `page`: `"reload"`, `"dialog.prompt"`. */
  path: string;
  /** The release it went in — half of every message this produces. */
  removedIn: string;
  /** What to write instead — the other half. */
  instead: string;
  /** `tombstone` while the name is still there as a thrower (one major); `gone` once deleted. */
  stage: "tombstone" | "gone";
}

/** Every `page` member ever removed. Empty, and adding to it is the whole ritual. */
export const REMOVALS: Removal[] = [];

const throwers = new Map<Removal, () => never>();
const warned = new Set<string>();

/** Wraps `page` so the removals list is answered; returns the object itself when the list is empty. */
export function withRemovals<Page extends object>(
  page: Page,
  removals: Removal[] = REMOVALS,
): Page {
  return removals.length ? (guard(page, "", removals) as Page) : page;
}

/** Test seam: the notices are once-per-session, and a session ends between tests. */
export function resetRemovalNotices() {
  warned.clear();
  throwers.clear();
}

// One Proxy per object that owns a removed name, built top down so `page.dialog`
// is guarded before anything reads a member off it.
function guard(target: any, prefix: string, removals: Removal[]): any {
  const here = new Map<string, Removal>();
  const below = new Map<string, Removal[]>();
  for (const removal of removals) {
    const [key, ...rest] = removal.path.slice(prefix.length).split(".");
    if (rest.length) below.set(key, [...(below.get(key) ?? []), removal]);
    else here.set(key, removal);
  }

  for (const [key, deeper] of below) {
    const child = target[key];
    if (child && typeof child === "object")
      target[key] = guard(child, `${prefix}${key}.`, deeper);
  }

  if (!here.size) return target;
  return new Proxy(target, {
    get(owner, key, receiver) {
      const removal = typeof key === "string" ? here.get(key) : undefined;
      if (!removal) return Reflect.get(owner, key, receiver);
      if (removal.stage === "gone") {
        warnRemoved(removal);
        return undefined;
      }
      return tombstone(removal);
    },
  });
}

// Memoized so a tombstone is the same function every read: a script that stashes
// `const open = page.dialog.prompt` must not get a different one each replay.
function tombstone(removal: Removal) {
  const existing = throwers.get(removal);
  if (existing) return existing;
  const thrower = () => reportAndThrow(removal);
  throwers.set(removal, thrower);
  return thrower;
}

// Not dev-gated: a removal firing is an upgrade breaking a site no developer is watching.
function reportAndThrow(removal: Removal): never {
  const source = runningSource();
  const error = new Error(`page.${removal.path} was ${detail(removal)}`);
  console.error(
    `[record-page] ${source} called page.${removal.path}, ${detail(removal)}`,
  );
  reportCustomizationError(error, {
    source,
    event: `removed:${removal.path}`,
  });
  toastScriptError(
    `removed:${source}:${removal.path}`,
    `${source} uses page.${removal.path}, ${detail(removal)}`,
  );
  throw error;
}

// Console only: probing is legitimate, and an Error Log row per probe is not cheap enough to be wrong about.
function warnRemoved(removal: Removal) {
  const source = runningSource();
  const message = `[record-page] ${source} read page.${removal.path}, ${detail(removal)}`;
  if (warned.has(message)) return;
  warned.add(message);
  console.warn(message);
}

function detail(removal: Removal) {
  return `removed in ${removal.removedIn} — use ${removal.instead}`;
}
