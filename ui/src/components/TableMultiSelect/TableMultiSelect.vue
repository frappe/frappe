<template>
	<MultiSelect
		v-model="model"
		:options="options"
		:label="label"
		:description="description"
		:placeholder="placeholder"
		:required="required"
		:disabled="disabled"
		:loading="search.loading && !search.data"
		@update:open="onOpen"
		@update:query="onQuery"
	>
		<!-- Selected links shown as white chips inside the subtle-variant trigger,
		     instead of MultiSelect's default "N selected" summary. -->
		<template #trigger="{ open, selectedOptions, toggleOpen }">
			<button
				type="button"
				:disabled="disabled"
				:data-state="open ? 'open' : 'closed'"
				class="flex min-h-7 w-full cursor-pointer items-center gap-1.5 rounded border border-[--surface-gray-2] bg-surface-gray-2 px-1.5 py-1 text-left text-ink-gray-7 outline-none transition-colors hover:border-outline-gray-modals hover:bg-surface-gray-3 focus-visible:ring-2 data-[state=open]:ring-2 ring-outline-gray-3 disabled:cursor-not-allowed disabled:bg-surface-gray-1 disabled:text-ink-gray-4"
				@click="toggleOpen"
			>
				<div class="flex min-w-0 flex-1 flex-wrap items-center gap-1">
					<span
						v-for="option in selectedOptions"
						:key="option.value"
						class="inline-flex h-7 items-center gap-1 rounded border border-outline-gray-1 bg-surface-white px-1.5 text-sm text-ink-gray-7 transition-colors hover:border-outline-gray-2 hover:bg-surface-gray-1"
					>
						{{ option.label }}
						<span
							v-if="!disabled"
							role="button"
							tabindex="-1"
							class="-mr-0.5 inline-flex cursor-pointer items-center justify-center rounded-sm p-0.5 opacity-70 hover:opacity-100"
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

		<!-- Footer: a "Create '{query}'" action (host-wired via `@create`) plus
		     Clear All. Rendered only when there's something to show, so no stray
		     bordered strip appears. -->
		<template #footer="{ clearAll, selectedOptions, query }">
			<div
				v-if="(creatable && !!query.trim()) || selectedOptions.length"
				class="flex items-center justify-between gap-2 border-t border-outline-gray-1 px-2 py-1.5"
			>
				<Button
					v-if="creatable && !!query.trim()"
					variant="ghost"
					size="sm"
					@click="emit('create', query)"
				>
					<template #prefix>
						<span class="lucide-plus size-4" />
					</template>
					Create "{{ query }}"
				</Button>
				<Button
					v-if="selectedOptions.length"
					variant="ghost"
					size="sm"
					class="ml-auto"
					@click="clearAll"
				>
					Clear All
				</Button>
			</div>
		</template>
	</MultiSelect>
</template>

<script setup lang="ts">
// Reusable link-backed multiselect: the role frappe-ui's `Link` plays for the
// single-value case, but for an array of link names. Owns the `search_link`
// resource, the white-chip trigger, and the optional `creatable` footer
// affordance — so field wrappers (lib's `TableMultiSelectField`, an app's
// override) stay thin and just bridge their stored shape to this `string[]`.
import { computed, watch } from "vue";
import { MultiSelect, Button, createResource, frappeRequest, debounce } from "frappe-ui";
import type {
	TableMultiSelectEmits,
	TableMultiSelectOption,
	TableMultiSelectProps,
} from "./types";

const props = withDefaults(defineProps<TableMultiSelectProps>(), {
	filters: () => ({}),
	disabled: false,
	creatable: false,
});

const emit = defineEmits<TableMultiSelectEmits>();

const model = defineModel<string[]>({ default: () => [] });

const search = createResource({
	url: "frappe.desk.search.search_link",
	params: { doctype: props.doctype, txt: "", filters: props.filters },
	method: "POST",
	resourceFetcher: frappeRequest,
	transform: (data: any[]): TableMultiSelectOption[] =>
		data.map((d) => ({ label: d.label || d.value, value: d.value })),
});

function loadOptions(txt = "") {
	if (!props.doctype) return;
	search.update({
		params: { txt, doctype: props.doctype, filters: props.filters },
	});
	search.reload();
}

function onOpen(isOpen: boolean) {
	if (isOpen) loadOptions("");
}

const onQuery = debounce((txt: string) => loadOptions(txt || ""), 300);

function removeTag(v: string) {
	model.value = model.value.filter((selected) => selected !== v);
}

// Keep already-selected values visible as options even when they're absent from
// the current search results — otherwise MultiSelect can't resolve their chips
// and the labels disappear from the trigger.
const options = computed<TableMultiSelectOption[]>(() => {
	const found = search.data ?? [];
	const present = new Set(found.map((o: TableMultiSelectOption) => o.value));
	const selectedOnly = model.value
		.filter((v) => !present.has(v))
		.map((v) => ({ label: v, value: v }));
	return [...selectedOnly, ...found];
});

watch([() => props.doctype, () => props.filters], () => loadOptions(""), {
	immediate: true,
	deep: true,
});
</script>
