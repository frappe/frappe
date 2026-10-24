<template>
	<MultiSelect
		v-model="model"
		:options="options"
		:label="label"
		:description="description"
		:placeholder="placeholder"
		:required="required"
		:disabled="disabled"
		:loading="search.loading.value && !search.data.value"
		:open="open"
		:query="query"
		@update:open="onOpen"
		@update:query="onQuery"
	>
		<!-- Selected links as white chips, replacing the default "N selected" summary. -->
		<template #trigger="{ open, selectedOptions, toggleOpen }">
			<button
				ref="trigger"
				type="button"
				:disabled="disabled"
				:data-state="open ? 'open' : 'closed'"
				class="flex min-h-7 w-full cursor-pointer items-center gap-1.5 rounded-4 border border-[--surface-gray-2] bg-surface-gray-2 px-1.5 py-1 text-left text-ink-gray-7 outline-none transition-colors hover:border-outline-elevation-2 hover:bg-surface-gray-3 focus-visible:ring-2 data-[state=open]:ring-2 ring-outline-gray-3 disabled:cursor-not-allowed disabled:bg-surface-gray-1 disabled:text-ink-gray-4"
				@click="toggleOpen"
			>
				<div class="flex min-w-0 flex-1 flex-wrap items-center gap-1">
					<span
						v-for="option in selectedOptions"
						:key="option.value"
						class="inline-flex h-7 items-center gap-1 rounded-4 border border-outline-gray-1 bg-surface-base px-1.5 text-sm text-ink-gray-7 transition-colors hover:border-outline-gray-2 hover:bg-surface-gray-1"
					>
						{{ option.label }}
						<span
							v-if="!disabled"
							role="button"
							tabindex="-1"
							class="-mr-0.5 inline-flex cursor-pointer items-center justify-center rounded-1 p-0.5 opacity-70 hover:opacity-100"
							@click.stop="removeTag(option.value)"
							@pointerdown.stop
						>
							<span class="lucide-x size-3" />
						</span>
					</span>

					<span v-if="!selectedOptions.length" class="px-1 text-base text-ink-gray-4">
						{{ placeholder ?? "Select" }}
					</span>
				</div>

				<span
					:class="[
						'lucide-chevron-down size-4 shrink-0 text-ink-gray-4 transition-transform',
						open && 'rotate-180',
					]"
				/>
			</button>
		</template>

		<!-- Footer: Create (via `@create`) and Clear All; hidden when empty. -->
		<template #footer="{ clear, close, selectedOptions, query }">
			<div
				v-if="creatable || selectedOptions.length"
				class="flex items-center justify-between gap-2 border-t border-outline-gray-1 px-2 py-1.5"
			>
				<Button v-if="creatable" variant="ghost" size="sm" @click="create(query, close)">
					<template #prefix>
						<span class="lucide-plus size-4" />
					</template>
					<slot name="create" :query="query">
						{{ query.trim() ? __('Create "{0}"', [query.trim()]) : __("Create") }}
					</slot>
				</Button>
				<Button
					v-if="selectedOptions.length"
					variant="ghost"
					size="sm"
					class="ml-auto"
					@click="clear"
				>
					Clear All
				</Button>
			</div>
		</template>
	</MultiSelect>
</template>

<script setup lang="ts">
// Link-backed multiselect: `Link` for an array of link names. Owns the
// link search, the white-chip trigger, and the `creatable` footer.
import { computed, ref, useTemplateRef, watch } from "vue";
import { MultiSelect, Button, debounce } from "frappe-ui";
import { useLinkSearch } from "../../composables/useLinkSearch";
import { translate as __ } from "../../utils/translate";
import type {
	TableMultiSelectEmits,
	TableMultiSelectExposed,
	TableMultiSelectOption,
	TableMultiSelectProps,
	TableMultiSelectSlots,
} from "./types";

const props = withDefaults(defineProps<TableMultiSelectProps>(), {
	filters: () => ({}),
	disabled: false,
	creatable: false,
});

const emit = defineEmits<TableMultiSelectEmits>();

defineSlots<TableMultiSelectSlots>();

const model = defineModel<string[]>({ default: () => [] });
const open = defineModel<boolean>("open", { default: false });
const trigger = useTemplateRef<HTMLButtonElement>("trigger");
// Held here because listening to `update:query` makes MultiSelect leave the query to us.
const query = ref("");

const search = useLinkSearch(
	() => props.doctype,
	() => props.filters
);

function loadOptions(txt = "", fresh = false) {
	void search.search(txt, { fresh });
}

function onOpen(isOpen: boolean) {
	open.value = isOpen;
	if (isOpen) loadOptions("");
}

function create(typed: string, close: () => void) {
	emit("create", typed);
	query.value = "";
	close();
}

const searchFor = debounce((txt: string) => loadOptions(txt || ""), 300);

function onQuery(txt: string) {
	query.value = txt;
	searchFor(txt);
}

function removeTag(v: string) {
	model.value = model.value.filter((selected) => selected !== v);
}

// Keep selected values in the options even when absent from search results, so
// MultiSelect can still resolve their chip labels.
const options = computed<TableMultiSelectOption[]>(() => {
	const found: TableMultiSelectOption[] = (search.data.value ?? []).map(({ label, value }) => ({
		label,
		value,
	}));
	const present = new Set(found.map((o) => o.value));
	const selectedOnly = model.value
		.filter((v) => !present.has(v))
		.map((v) => ({ label: props.titles?.[v] ?? v, value: v }));
	return [...selectedOnly, ...found];
});

watch([() => props.doctype, () => props.filters], () => loadOptions(""), {
	immediate: true,
	deep: true,
});

defineExpose<TableMultiSelectExposed>({
	search: (text, { fresh = false } = {}) => loadOptions(text, fresh),
	focus: () => trigger.value?.focus(),
});
</script>
