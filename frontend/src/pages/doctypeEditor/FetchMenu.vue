<!-- The Fetch from list, in two steps: a Link field of this DocType, then a field of the DocType it
     links to. With `link`, it starts and stays on that Link's fields ("Fetch a field…"). -->
<template>
	<div class="flex w-[320px] flex-col" data-fetch-menu @keydown.esc.stop="$emit('close')">
		<div class="flex items-center gap-1 border-b border-outline-gray-1 p-1.5">
			<Button
				v-if="step && !link"
				variant="ghost"
				icon="lucide-chevron-left"
				:aria-label="__('Back to Link fields')"
				data-fetch-back
				@click="open(null)"
			/>
			<TextInput
				ref="search"
				v-model="query"
				class="min-w-0 flex-1"
				variant="ghost"
				:placeholder="
					step ? __('Search fields of {0}', [step.options]) : __('Search Link fields')
				"
				autocomplete="off"
				@keydown.enter.prevent="pickFirst"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
				</template>
			</TextInput>
		</div>
		<p class="truncate px-3.5 pb-1 pt-2 text-sm text-ink-gray-5">
			{{ step ? __("Fields of {0}", [step.options]) : __("Link fields of this DocType") }}
		</p>
		<div class="max-h-[300px] overflow-y-auto p-1.5 pt-0">
			<template v-if="!step">
				<button
					v-for="one in shownLinks"
					:key="one.fieldname"
					type="button"
					class="flex h-7 w-full min-w-0 items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-8 hover:bg-surface-gray-3"
					:data-fetch-link="one.fieldname"
					@click="open(one)"
				>
					<span class="lucide-link size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
					<span class="min-w-0 truncate">{{ one.label || one.fieldname }}</span>
					<span
						class="min-w-0 flex-1 basis-0 truncate pl-2 text-right text-sm text-ink-gray-5"
					>
						{{ one.options }}
					</span>
					<span
						class="lucide-chevron-right size-4 shrink-0 text-ink-gray-4"
						aria-hidden="true"
					/>
				</button>
				<p v-if="!shownLinks.length" class="px-2 py-1.5 text-base text-ink-gray-5">
					{{
						links.length
							? __("No Link field matches")
							: __("This DocType has no Link field yet")
					}}
				</p>
			</template>
			<template v-else>
				<p v-if="note" class="px-2 py-1.5 text-p-sm text-ink-gray-5" data-fetch-note>
					{{ note }}
				</p>
				<button
					v-for="one in shownSources"
					:key="one.fieldname"
					type="button"
					class="flex h-7 w-full min-w-0 items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-8 hover:bg-surface-gray-3"
					:data-fetch-source="one.fieldname"
					@click="$emit('pick', step, one)"
				>
					<span
						:class="[
							typeIcon(typeName(one.fieldtype, one.options)),
							'size-4 shrink-0 text-ink-gray-5',
						]"
						aria-hidden="true"
					/>
					<span class="min-w-0 truncate">{{ one.label || one.fieldname }}</span>
					<span
						v-if="chosen(one)"
						class="lucide-check ml-auto size-4 shrink-0 text-ink-gray-7"
						:aria-label="__('Chosen')"
					/>
				</button>
				<p
					v-if="!note && !shownSources.length"
					class="px-2 py-1.5 text-base text-ink-gray-5"
				>
					{{ __("No field matches") }}
				</p>
			</template>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { Button, TextInput } from "frappe-ui";
import { isApiError } from "@framework/ui/api";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { __ } from "@/i18n";
import { fetchSources, parseFetchFrom } from "./fetchFrom";
import { typeIcon, typeName } from "./fieldtypes";

const props = defineProps<{
	links: RawMetaField[];
	/** The field's `fetch_from`: the menu opens on its Link and checks its field. */
	value?: string;
	link?: RawMetaField;
}>();
const emit = defineEmits<{ pick: [link: RawMetaField, source: RawMetaField]; close: [] }>();

const current = parseFetchFrom(props.value);
const step = ref(props.link ?? props.links.find((one) => one.fieldname === current?.link) ?? null);
const query = ref("");
const search = ref<{ focus: () => void } | null>(null);

const { meta, loading, error } = useDoctypeMeta(() => step.value?.options ?? "");
const sources = computed(() => fetchSources(meta.value?.fields ?? []));
const shownLinks = computed(() => props.links.filter(matches));
const shownSources = computed(() => sources.value.filter(matches));
const note = computed(() => {
	const doctype = step.value?.options;
	if (loading.value) return __("Loading fields of {0}…", [doctype]);
	if (isApiError(error.value) && error.value.status === 403) {
		return __("You cannot read {0}, so its fields cannot be fetched.", [doctype]);
	}
	return error.value ? __("The fields of {0} did not load.", [doctype]) : "";
});

onMounted(focus);

function matches(one: RawMetaField) {
	const text = `${one.label ?? ""} ${one.fieldname} ${one.options ?? ""}`.toLowerCase();
	return text.includes(query.value.trim().toLowerCase());
}

function chosen(one: RawMetaField) {
	return step.value?.fieldname === current?.link && one.fieldname === current?.source;
}

function open(one: RawMetaField | null) {
	step.value = one;
	query.value = "";
	focus();
}

function pickFirst() {
	if (!step.value) return shownLinks.value[0] && open(shownLinks.value[0]);
	const first = shownSources.value[0];
	if (first) emit("pick", step.value, first);
}

function focus() {
	void nextTick(() => search.value?.focus());
}
</script>
