// The tag picker's editing session: ticks change a local draft, and one batch goes out when it ends.
import { computed, ref } from "vue";
import { listDiff } from "./people";

/** Chips drawn before "+N more". */
export const VISIBLE_TAGS = 3;

export type TagBatch = { added: { tag: string; color?: string }[]; removed: string[] };

/** What the draft adds and drops against the tags the session opened with; a new tag brings its colour. */
export function tagBatch(base: string[], draft: string[], colors: ReadonlyMap<string, string>): TagBatch {
	const { added, dropped } = listDiff(draft, base);
	return { added: added.map((tag) => ({ tag, color: colors.get(tag) })), removed: dropped };
}

/** The chips to draw and the names behind "+N more"; it collapses only past one more than fits, so "+1 more" never hides one chip. */
export function splitTags(tags: string[]) {
	const collapsed = tags.length > VISIBLE_TAGS + 1;
	const shown = collapsed ? tags.slice(0, VISIBLE_TAGS) : tags;
	return { shown, hidden: tags.slice(shown.length) };
}

/** The applied tags first, then A to Z. */
export function appliedFirst<Option extends { value: string }>(options: Option[], applied: string[]): Option[] {
	const rank = (option: Option) => (applied.includes(option.value) ? 0 : 1);
	return [...options].sort((a, b) => rank(a) - rank(b) || a.value.localeCompare(b.value));
}

/** `write` sends a batch and settles once the record shows the server's answer; `recolour` saves a tag's colour at once. */
export function useTagSession(serverTags: () => string[], write: (batch: TagBatch) => Promise<void>,
	recolour: (tag: string, color: string) => Promise<void>
) {
	const draft = ref<string[] | null>(null);
	const base = ref<string[]>([]);
	const colors = new Map<string, string>();

	const tags = computed(() => draft.value ?? serverTags());
	const listed = computed(() => [...new Set([...base.value, ...tags.value])]);

	function begin() {
		if (draft.value) return;
		base.value = [...serverTags()];
		draft.value = [...base.value];
	}

	function set(next: string[]) {
		draft.value = next;
	}

	function addNew(tag: string, color: string) {
		colors.set(tag, color);
		if (!draft.value?.includes(tag)) draft.value = [...(draft.value ?? []), tag];
	}

	async function commit() {
		const batch = tagBatch(base.value, draft.value ?? [], colors);
		colors.clear();
		try {
			if (batch.added.length || batch.removed.length) await write(batch);
		} finally {
			draft.value = null;
		}
	}

	async function remove(tag: string) {
		begin();
		set((draft.value ?? []).filter((name) => name !== tag));
		await commit();
	}

	return { tags, listed, base, begin, set, addNew, commit, remove, recolour };
}

export type TagSession = ReturnType<typeof useTagSession>;
