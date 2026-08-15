import { withKeys, withModifiers } from "vue"

type EventHandler = (...args: any[]) => any

export interface ResolvedEvent {
	name: string
	listener: EventHandler
}

// Guard modifiers handled by Vue's `withModifiers` (event-level behaviour).
const SYSTEM_MODIFIERS = ["stop", "prevent", "self", "exact", "ctrl", "shift", "alt", "meta", "left", "middle", "right"]

/**
 * Parse a Vue-style event name with modifiers (e.g. "keydown.enter", "click.prevent")
 * into a base event name and a handler wrapped with the matching guards.
 *
 * The template compiler normally applies this `@event.modifier` sugar, but it does
 * not run for listeners bound dynamically through `v-on="object"`, so we reproduce
 * it here. Key modifiers go through `withKeys`, the rest through `withModifiers`.
 */
export function resolveEventListener(
	rawName: string,
	handler: EventHandler,
	emits: string[] | Record<string, any> = [],
): ResolvedEvent {
	const emitNames = Array.isArray(emits) ? emits : Object.keys(emits)
	if (emitNames.includes(rawName)) return { name: rawName, listener: handler }

	const [name, ...modifiers] = rawName.split(".")
	if (!modifiers.length) return { name, listener: handler }

	const isKeyboardEvent = name.startsWith("key")
	const guards: string[] = []
	const keys: string[] = []

	for (const modifier of modifiers) {
		if (!modifier) continue
		// `left` / `right` are arrow keys on keyboard events but mouse buttons elsewhere
		const isAmbiguous = modifier === "left" || modifier === "right"
		if (SYSTEM_MODIFIERS.includes(modifier) && !(isKeyboardEvent && isAmbiguous)) {
			guards.push(modifier)
		} else {
			keys.push(modifier)
		}
	}

	let listener = handler
	if (guards.length) listener = withModifiers(listener, guards as any)
	if (keys.length) listener = withKeys(listener, keys)
	return { name, listener }
}
