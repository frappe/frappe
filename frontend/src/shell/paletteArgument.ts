// An act's argument step: the act as a chip, and its options for the query; picking one runs it.
import { computed, ref, shallowRef, watch, type Ref } from "vue";
import { refDebounced } from "@vueuse/core";
import { acts, type ActOption } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { paletteArgument, paletteOpen, type PaletteRow } from "./palette";
import { rank } from "./paletteRanking";

const PAUSE_MS = 200;
const MAX_ROWS = 50;

/** The act whose argument the palette asks for, its options ranked by the query, and the way back. */
export function usePaletteArgument(query: Ref<string>) {
	const act = computed(() => (paletteArgument.value ? acts.find(paletteArgument.value) : undefined));
	const text = computed(() => query.value.trim());
	const settled = refDebounced(text, PAUSE_MS);
	const options = shallowRef<ActOption[]>([]);
	const waiting = ref(false);
	const failed = ref(false);
	const asked = shallowRef<{ text: string } | null>(null);

	// Each open starts the step afresh; a closing palette keeps its rows as it fades.
	watch(
		[paletteArgument, paletteOpen],
		([name, isOpen]) => {
			if (!isOpen) return;
			asked.value = null;
			options.value = [];
			failed.value = false;
			waiting.value = false;
			query.value = "";
			if (name) ask("");
		},
		{ immediate: true }
	);
	watch(settled, (typed) => {
		if (paletteOpen.value && paletteArgument.value && asked.value?.text !== typed) ask(typed);
	});
	// A page that lets go of the act while its step shows takes the step with it.
	watch(
		() => Boolean(paletteArgument.value && !act.value),
		(gone) => gone && leave()
	);

	function ask(typed: string) {
		const argument = act.value?.argument;
		if (!argument) return;
		const ticket = { text: typed };
		asked.value = ticket;
		let reply: ActOption[] | Promise<ActOption[]>;
		try {
			reply = argument.options(typed);
		} catch (error) {
			return refuse(ticket, error);
		}
		if (Array.isArray(reply)) return answer(ticket, reply);
		waiting.value = true;
		Promise.resolve(reply).then(
			(found) => answer(ticket, found),
			(error) => refuse(ticket, error)
		);
	}

	// An older reply that lands after a newer ask is dropped.
	function answer(ticket: { text: string }, found: ActOption[]) {
		if (asked.value !== ticket) return;
		options.value = found;
		failed.value = false;
		waiting.value = false;
	}

	function refuse(ticket: { text: string }, error: unknown) {
		if (asked.value !== ticket) return;
		console.error("[frappe] the palette could not read an act's options", error);
		options.value = [];
		failed.value = true;
		waiting.value = false;
	}

	const rows = computed<PaletteRow[]>(() => {
		const name = paletteArgument.value;
		if (!name || !act.value) return [];
		const ranked = rank(
			options.value.map((option) => optionRow(name, option)),
			text.value
		).slice(0, MAX_ROWS);
		const behind = waiting.value || asked.value?.text !== text.value;
		if (!ranked.length && behind && !failed.value)
			return [{ id: "searching", label: __("Searching…"), pending: true, run: () => {} }];
		return ranked;
	});

	/** What the empty list says when the options could not be read, or there are none. */
	const prompt = computed(() => {
		if (!act.value || rows.value.length) return null;
		if (failed.value) return __("Could not load {0}", [act.value.argument!.label]);
		if (!options.value.length && !text.value) return __("Nothing to choose from");
		return null;
	});

	function leave() {
		paletteArgument.value = null;
		query.value = "";
	}

	return { act, rows, prompt, leave };
}

function optionRow(name: string, option: ActOption): PaletteRow {
	return {
		id: `option:${keyOf(option.value)}`,
		label: option.label,
		description: option.description,
		icon: option.icon,
		image: option.image,
		disabled: Boolean(option.disabled),
		hint: option.disabled,
		keywords: [option.description, typeof option.value === "string" ? option.value : undefined].filter(
			(word): word is string => !!word
		),
		run: () => acts.perform(name, option.value),
	};
}

function keyOf(value: unknown) {
	return typeof value === "object" && value !== null ? JSON.stringify(value) : String(value);
}
