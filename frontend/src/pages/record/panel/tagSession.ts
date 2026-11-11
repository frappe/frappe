// The tag picker's editing session: ticks change a local draft, and one batch goes out when it ends.
import { computed, ref } from "vue";
import { listDiff } from "./people";

/** Chips drawn before "+N more". */
export const VISIBLE_TAGS = 3;

export type TagBatch = { added: { tag: string; color?: string }[]; removed: string[] };

/** What the draft adds and drops against the base; a new tag brings its colour. */
export function tagBatch(base: string[], draft: string[], colors: ReadonlyMap<string, string>): TagBatch {
	const { added, dropped } = listDiff(draft, base);
	return { added: added.map((tag) => ({ tag, color: colors.get(tag) })), removed: dropped };
}

/** The chips to draw and the names behind "+N more"; never "+1 more", which would hide one chip. */
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
	let queue: Promise<void> = Promise.resolve();

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

	// Writes run one after another; a reopened session diffs against what the last commit sent.
	function commit(): Promise<void> {
		const snapshot = draft.value;
		if (!snapshot) return queue;
		const batch = tagBatch(base.value, snapshot, colors);
		colors.clear();
		base.value = [...snapshot];
		const run = async () => {
			try {
				if (batch.added.length || batch.removed.length) await write(batch);
			} finally {
				if (draft.value === snapshot) {
					draft.value = null;
					base.value = [...serverTags()];
				}
			}
		};
		queue = queue.then(run, run);
		return queue;
	}

	async function remove(tag: string) {
		begin();
		draft.value = (draft.value ?? []).filter((name) => name !== tag);
		await commit();
	}

	// A tag the last commit is still creating has no Tag row to recolour yet.
	const recolourAfterWrites = async (tag: string, color: string) => {
		await queue;
		await recolour(tag, color);
	};

	return { tags, listed, base, begin, set, addNew, commit, remove, recolour: recolourAfterWrites };
}

export type TagSession = ReturnType<typeof useTagSession>;
