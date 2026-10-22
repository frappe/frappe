import { computed, markRaw, reactive, ref, toRaw } from "vue"

const isComponentLike = (value: unknown): value is object =>
	Boolean(value) &&
	typeof value === "object" &&
	("render" in (value as object) || "setup" in (value as object) || "__name" in (value as object))

// items live in a reactive Map, which would proxy the component definitions they
// carry (a tab's panel, a control, an icon) and make Vue warn on every render
function withRawComponents<T extends object>(item: T): T {
	for (const [key, value] of Object.entries(item)) {
		if (isComponentLike(value)) {
			(item as Record<string, unknown>)[key] = markRaw(value)
		} else if (Array.isArray(value)) {
			value.forEach((entry) => entry && typeof entry === "object" && withRawComponents(entry))
		}
	}
	return item
}

/**
 * Every registry item needs a stable identity, and may ask for a position
 * relative to another item's name.
 *
 * An unknown `before` name puts the item first, an unknown `after` name puts it
 * last, so an extension that anchors to a feature this site does not have still
 * lands somewhere sensible.
 */
export type RegistryEntry = {
	name: string
	before?: string
	after?: string
}

/** The common case: the surface itself decides whether an item shows. */
export type RegistryItem = RegistryEntry & {
	condition?: () => boolean
}

/**
 * A registry backs one editor surface. Built-in features and, later, extensions
 * register through the same function.
 *
 * Leave `before` and `after` unset in the common case: items then display in
 * registration order.
 *
 * Read `visible` when an item decides its own visibility. Read `all` when the
 * surface passes an argument to condition, as the block context menu does.
 */
export function createRegistry<T extends RegistryEntry>() {
	const items = reactive(new Map<string, T>()) as Map<string, T>
	const order = ref<string[]>([])

	// re-registering without an anchor keeps the slot the name already holds, so
	// installing the same set twice cannot reshuffle the surface
	const place = (item: T) => {
		const current = order.value.indexOf(item.name)
		if (current !== -1) {
			if (!item.before && !item.after) return
			order.value.splice(current, 1)
		}
		if (item.before) {
			const anchor = order.value.indexOf(item.before)
			order.value.splice(anchor === -1 ? 0 : anchor, 0, item.name)
		} else if (item.after) {
			const anchor = order.value.indexOf(item.after)
			if (anchor === -1) order.value.push(item.name)
			else order.value.splice(anchor + 1, 0, item.name)
		} else {
			order.value.push(item.name)
		}
	}

	const remove = (name: string) => {
		const position = order.value.indexOf(name)
		if (position !== -1) order.value.splice(position, 1)
		return items.delete(name)
	}

	// returns its own unregister, so a caller never has to track names
	const register = (item: T) => {
		const registered = withRawComponents({ ...item })
		items.set(item.name, registered)
		place(registered)
		// a later registration under the same name owns the entry, so this must not delete it
		return () => {
			if (toRaw(items.get(item.name)) === registered) remove(item.name)
		}
	}

	const all = computed(() => order.value.map((name) => items.get(name) as T))

	// condition runs at render, never at register, so it can read live state
	const visible = computed(() => all.value.filter((item) => (item as RegistryItem).condition?.() ?? true))

	return { register, unregister: remove, all, visible }
}
