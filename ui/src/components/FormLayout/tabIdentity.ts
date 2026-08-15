import type { Tab } from "./types";

/**
 * A tab is addressed by a stable *identity* — never by its position. Identity is
 * what the strip remembers, so the reader keeps their place when a `depends_on`
 * tab appears or disappears beside them, and when the whole form is torn down and
 * rebuilt on save.
 *
 * `FormLayout` resolves identity itself and guarantees it is unique within the
 * strip, rather than trusting the tabs it is handed: `name` is optional and no
 * writer enforces uniqueness, and a component with several unrelated hosts cannot
 * check an invariant none of them promises.
 */

/** `name` if the author wrote one, else the label slugified, else the position. */
function baseIdentity(tab: Pick<Tab, "name" | "label">, index: number): string {
  return tab.name || slug(tab.label ?? "") || `tab-${index + 1}`;
}

function slug(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Stamp each tab with its `identity`, suffixing collisions deterministically
 * (`details`, `details-2`, `details-3`) so the same strip always resolves the
 * same way. `identity` is deliberately *not* `name`: `name` stays "what the
 * author wrote", `identity` is "what the strip addresses".
 */
export function identifyTabs<T extends Pick<Tab, "name" | "label">>(
  tabs: T[]
): (T & { identity: string })[] {
  const taken = new Set<string>();
  return tabs.map((tab, index) => {
    const base = baseIdentity(tab, index);
    let identity = base;
    for (let suffix = 2; taken.has(identity); suffix++)
      identity = `${base}-${suffix}`;
    taken.add(identity);
    return { ...tab, identity };
  });
}
