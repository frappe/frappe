// The shell binds the `key` of each act available now through `useKeyboardShortcut`; a press runs
// the act through the dispatcher, so its checks run as they do for a click.
import { computed, defineComponent, h, watch, type PropType } from "vue";
import { useKeyboardShortcut, type KeyboardShortcutCombo } from "frappe-ui";
import { acts, type ActItem, type AvailableAct } from "@/acts/dispatcher";
import { overlayOf } from "./overlay";

/** Opens the palette at an act's argument step; without it, a key on an act with an argument is not bound. */
export type OpenArgument = (act: AvailableAct) => void;

/** Binds every available act's key while mounted; where acts share a combo, a page act wins over a shell act. */
export const ActKeys = defineComponent({
	name: "ActKeys",
	props: {
		openArgument: { type: Function as PropType<OpenArgument>, default: undefined },
	},
	setup(props) {
		const bindings = computed(() => {
			const bound = (item: ActItem) => Boolean(item.key && (!item.argument || props.openArgument));
			return actsByCombo(acts.available(bound));
		});
		watch(bindings, warnOnCollisions, { immediate: true });

		function press(act: AvailableAct) {
			if (act.argument) props.openArgument?.(act);
			else void acts.perform(act.name);
		}

		return () =>
			[...bindings.value.values()].map(([act]) =>
				h(ActKey, { key: `${act.key} ${act.name}`, act, onPress: press })
			);
	},
});

/** One combo's registration, for the act that holds it now. */
const ActKey = defineComponent({
	name: "ActKey",
	props: {
		act: { type: Object as PropType<AvailableAct>, required: true },
	},
	emits: { press: (_act: AvailableAct) => true },
	setup(props, { emit }) {
		const combo = props.act.key!;
		const command = typesNothing(combo);
		useKeyboardShortcut({
			combo: combo as KeyboardShortcutCombo,
			description: props.act.label ?? props.act.name,
			allowInInput: command,
			allowInDialog: command,
			preventDefault: false,
			handler: (event) => {
				// In an overlay a Mod combo runs nothing, yet still keeps the browser's own Mod+S off the page.
				if (overlayOf(event.target)) return void (command && event.preventDefault());
				event.preventDefault();
				if (!event.repeat) emit("press", props.act);
			},
		});
		return () => null;
	},
});

function actsByCombo(available: AvailableAct[]) {
	const byCombo = new Map<string, AvailableAct[]>();
	for (const act of available) {
		const combo = canonical(act.key!);
		byCombo.set(combo, [...(byCombo.get(combo) ?? []), act]);
	}
	for (const holders of byCombo.values()) holders.sort((a, b) => rank(a) - rank(b));
	return byCombo;
}

function rank(act: AvailableAct) {
	return act.name.startsWith("shell.") ? 1 : 0;
}

const warned = new Set<string>();

function warnOnCollisions(bindings: Map<string, AvailableAct[]>) {
	if (!import.meta.env.DEV) return;
	for (const holders of bindings.values()) {
		if (holders.length < 2) continue;
		const names = holders.map((act) => act.name);
		const message = `${holders[0].key} is the key of ${names.join(", ")}; ${names[0]} runs`;
		if (warned.has(message)) continue;
		warned.add(message);
		console.warn(`[acts] ${message}`);
	}
}

/** One spelling per physical combo: `useKeyboardShortcut` reads modifiers in any order and any case. */
function canonical(combo: string) {
	const parts = combo.split("+").map((part) => part.trim().toLowerCase());
	const key = parts.pop();
	return [...parts.sort(), key].join("+");
}

/** A combo with Mod or Ctrl types no text, so it fires while a field or a dialog has focus. */
function typesNothing(combo: string) {
	return canonical(combo).split("+").slice(0, -1).some((modifier) => modifier === "mod" || modifier === "ctrl");
}
