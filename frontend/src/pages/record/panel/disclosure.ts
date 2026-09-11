// The reader's disclosure of the panel's sections: open or shut, remembered per doctype
// through the shell's section memory, so one concept has one store in this desk.
import { computed, reactive, ref, type MaybeRefOrGetter, toValue } from "vue";
import { sectionMemory } from "@/navigation/sectionMemory";

export interface DisclosedSection {
	name: string;
	/** Where the section starts, as the layout or the script that added it says. */
	opened: boolean;
}

export interface Disclosure {
	isOpen(name: string): boolean;
	/** The reader's decision: remembered, and it wins over a script's act. */
	set(name: string, open: boolean): void;
	toggle(name: string): void;
	/** A script's act: in-page state for this record, never written as the reader's. */
	disclose(name: string, open: boolean): void;
	/** Drops every act, for the next record. */
	reset(): void;
}

/**
 * One reader's open sections for one container. The memory is rebuilt whenever the
 * sections change, so a section a replay adds is remembered and one it drops is pruned.
 */
export function useDisclosure(
	user: MaybeRefOrGetter<string>,
	container: MaybeRefOrGetter<string>,
	sections: MaybeRefOrGetter<DisclosedSection[]>
): Disclosure {
	// The memory reads storage once; a write here bumps it so `isOpen` re-reads.
	const version = ref(0);
	const acts = reactive(new Map<string, boolean>());

	const memory = computed(() => {
		version.value;
		return sectionMemory(
			toValue(user),
			toValue(container),
			toValue(sections).map((section) => ({
				key: section.name,
				keep_closed: section.opened ? undefined : 1,
			}))
		);
	});

	const defaults = computed(
		() => new Map(toValue(sections).map((section) => [section.name, section.opened]))
	);

	function isOpen(name: string) {
		return acts.get(name) ?? memory.value.recall(name) ?? defaults.value.get(name) ?? true;
	}

	function set(name: string, open: boolean) {
		acts.delete(name);
		memory.value.remember(name, open);
		version.value++;
	}

	return {
		isOpen,
		set,
		toggle: (name) => set(name, !isOpen(name)),
		disclose: (name, open) => void acts.set(name, open),
		reset: () => acts.clear(),
	};
}
