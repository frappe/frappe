import {
	computed,
	defineComponent,
	markRaw,
	provide,
	ref,
	shallowRef,
	unref,
	type Component,
	type SetupContext,
} from "vue"
import type { StudioComponent, StudioComponentInput } from "@/types/Studio/StudioComponent"

/** A component script's default export: a Vue component definition without a template. */
export interface ComponentScript {
	props?: string[] | Record<string, any>
	emits?: string[] | Record<string, any>
	setup?: (props: Record<string, any>, context: SetupContext) => unknown
}

const SCRIPT_KEYS = ["props", "emits", "setup"]
const SCRIPT_SHAPE = "export default { props, emits, setup(props, { emit }) {} }"

/** Return the script, or throw an error that names what the script must export. */
export function validateComponentScript(script: unknown): ComponentScript {
	if (!script || typeof script !== "object" || Array.isArray(script)) {
		throw new Error(`A component script must export an object: ${SCRIPT_SHAPE}`)
	}
	const unknownKeys = Object.keys(script).filter((key) => !SCRIPT_KEYS.includes(key))
	if (unknownKeys.length) {
		throw new Error(
			`A component script cannot use "${unknownKeys.join('", "')}". Use only props, emits and setup.`,
		)
	}
	if ("setup" in script && typeof script.setup !== "function") {
		throw new Error("setup in a component script must be a function.")
	}
	return script
}

/**
 * Create the Vue component that a Studio Component mounts as. The caller renders the block tree
 * in the default slot.
 *
 * Vue validates props, applies their defaults and calls the listeners of emitted events only for
 * a component it mounts, so the script's props and emits go on this component. The script's
 * setup runs inside this component's setup, which lets it return a promise without <Suspense>.
 * A component without a script takes its props from its inputs.
 */
export function createComponentHost(
	component: Pick<StudioComponent, "component_id" | "inputs">,
	script: ComponentScript | null,
	onError: (error: unknown) => void = () => {},
): Component {
	return markRaw(
		defineComponent({
			name: component.component_id,
			inheritAttrs: false,
			props: script?.props ?? getPropsFromInputs(component.inputs),
			emits: script?.emits,
			setup(props, context) {
				const bindings = shallowRef<Record<string, any>>({})
				const ready = ref(false)

				function applyBindings(result: unknown) {
					if (typeof result === "function") return fail(new Error("setup must return an object."))
					bindings.value = (result as Record<string, any>) || {}
					ready.value = true
				}

				function fail(error: unknown) {
					console.error(`Error running the script of component ${component.component_id}`, error)
					onError(error)
					ready.value = true
				}

				try {
					const result = script?.setup?.(props, context)
					if (result instanceof Promise) result.then(applyBindings, fail)
					else applyBindings(result)
				} catch (error) {
					fail(error)
				}

				// Expressions read values, as a Vue template does.
				provide(
					"componentContext",
					computed(() => ({ inputs: props, ...unwrapRefs(bindings.value) })),
				)
				// Event scripts and two-way bindings need the refs to write to them.
				provide(
					"componentScriptContext",
					computed(() => ({ inputs: props, ...bindings.value })),
				)

				return () => (ready.value ? context.slots.default?.() : null)
			},
		}),
	)
}

function unwrapRefs(bindings: Record<string, any>): Record<string, any> {
	return Object.fromEntries(Object.entries(bindings).map(([name, binding]) => [name, unref(binding)]))
}

// A null type accepts any value, as inputs did before components had scripts.
function getPropsFromInputs(inputs: StudioComponentInput[] = []): Record<string, null> {
	return Object.fromEntries(inputs.map((input) => [input.input_name, null]))
}

/** The editor's description of each prop: the control that edits it, its default and its help text. */
export function getInputsFromProps(props: ComponentScript["props"] = {}): StudioComponentInput[] {
	if (Array.isArray(props)) return props.map((name) => ({ input_name: name, type: "text" }))
	return Object.entries(props).map(([name, prop]) => {
		const options = prop && typeof prop === "object" && !Array.isArray(prop) ? prop : { type: prop }
		const studio = options.studio || {}
		return {
			input_name: name,
			type: studio.type || getInputType(options.type),
			description: studio.description,
			options: studio.options?.join("\n"),
			required: options.required ? 1 : 0,
			default: getInputDefault(options.default),
		}
	})
}

function getInputType(propType: unknown): string {
	const type = Array.isArray(propType) ? propType[0] : propType
	if (type === String) return "text"
	if (type === Number) return "number"
	if (type === Boolean) return "checkbox"
	return "code"
}

// An input row stores its default as text. Object defaults come from a factory, which only Vue calls.
function getInputDefault(value: unknown): string | undefined {
	if (typeof value === "string") return value
	if (typeof value === "number" || typeof value === "boolean") return String(value)
}
