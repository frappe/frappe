<!-- A tag picker with a create row: a pick adds, an unpick removes. The trigger is the "+"
     chip among the record's tags, whatever the slot supplies, or a bare anchor when
     something else does the opening. -->
<template>
	<!-- `open` is bound only for the anchor: an undefined boolean prop reads as false. -->
	<MultiSelect
		v-bind="anchored ? { open } : {}"
		:modelValue="tags"
		:query="query"
		:options="options"
		:loading="loading"
		:filterable="false"
		:empty-text="error || 'No tags found'"
		placeholder="Search or create tags"
		:side="vertical ? 'left' : 'bottom'"
		@update:modelValue="retag"
		@update:query="onQuery"
		@update:open="(opened: boolean) => (open = opened)"
	>
		<template #trigger>
			<!-- It only positions the popover; taking clicks would swallow the trigger it covers. -->
			<div v-if="anchored" class="pointer-events-none absolute inset-0" aria-hidden="true" />
			<slot v-else name="trigger">
				<button
					type="button"
					class="grid size-5 place-content-center rounded-full text-sm text-ink-gray-5 transition hover:bg-surface-gray-3 hover:text-ink-gray-8"
					aria-label="Add tag"
					data-add-tag
				>
					<span class="lucide-plus size-3.5" aria-hidden="true" />
				</button>
			</slot>
		</template>

		<template #item-prefix="{ item }">
			<span
				class="size-2 shrink-0 rounded-full"
				:class="tagColor(item.label)"
				aria-hidden="true"
			/>
		</template>

		<template #footer>
			<button
				v-if="canCreate"
				type="button"
				class="flex w-full items-center gap-2 rounded-1 px-2 py-1.5 text-base text-ink-gray-6 hover:bg-surface-gray-2"
				data-create-tag
				@click="create()"
			>
				<span class="lucide-plus size-3.5 shrink-0" aria-hidden="true" />
				<span class="truncate">Create “{{ query.trim() }}”</span>
			</button>
		</template>
	</MultiSelect>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { MultiSelect } from "frappe-ui";
import { canCreateTag, listDiff, matchingTags, tagColor } from "./people";
import { useTagSearch, type SearchOption } from "./remoteSearch";

const props = defineProps<{
	doctype: string;
	tags: string[];
	call: (method: string, params?: Record<string, any>) => Promise<any>;
	/** Opens beside the collapsed strip instead of below. */
	vertical?: boolean;
	/** Overlays whatever it sits on and opens from `open` alone. */
	anchored?: boolean;
}>();

const emit = defineEmits<{ add: [string]; remove: [string] }>();

// Left undefined the picker owns its own open state, which is what every trigger but the anchor wants.
const open = defineModel<boolean | undefined>("open", { default: undefined });

const query = ref("");

// The record's own tags fill the gaps a paged answer leaves, so one already on it is never offered as new.
const pinned = computed<SearchOption[]>(() =>
	matchingTags(props.tags, query.value).map((tag) => ({ label: tag, value: tag }))
);

const { options, loading, error, search, searchSoon } = useTagSearch(
	props.call,
	props.doctype,
	pinned
);

// Listening to the query owns it, so every open resets it and the list. Watched, not
// handled: opened from the anchor, the picker never fires update:open.
watch(open, (opened) => {
	if (!opened) return;
	query.value = "";
	search("");
});

function onQuery(text: string) {
	query.value = text;
	searchSoon(text);
}

const canCreate = computed(() =>
	canCreateTag(
		options.value.map((option) => option.value),
		query.value
	)
);

// The selection is server state: each pick fires one write and the re-read repaints it.
function retag(picked: (string | number)[]) {
	const { added, dropped } = listDiff(picked.map(String), props.tags);
	added.forEach((tag) => emit("add", tag));
	dropped.forEach((tag) => emit("remove", tag));
}

function create() {
	emit("add", query.value.trim());
	query.value = "";
	search("");
}
</script>
