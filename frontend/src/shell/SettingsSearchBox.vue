<!-- The search box above the settings pane list, and its results, which replace the list while a
     query is typed: the framework's and the current app's matches, then other apps'. -->
<template>
	<div class="-mb-2">
		<TextInput
			ref="input"
			v-model="query"
			variant="outline"
			:placeholder="__('Search settings')"
			:aria-label="__('Search settings')"
			@keydown.down.prevent="move(1)"
			@keydown.up.prevent="move(-1)"
			@keydown.enter.prevent="hits[active] && emit('pick', hits[active])"
		>
			<template #prefix>
				<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
			</template>
			<template v-if="query" #suffix>
				<button
					type="button"
					:aria-label="__('Clear search')"
					class="grid size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
					@click="clear"
				>
					<span class="lucide-x size-3.5" aria-hidden="true" />
				</button>
			</template>
		</TextInput>
	</div>
	<div v-if="search && query.trim()" ref="list" class="flex flex-col gap-4">
		<p v-if="!hits.length" class="px-2 text-base text-ink-gray-5">
			{{ __("No settings match “{0}”", [query.trim()]) }}
		</p>
		<SettingsNavGroup
			v-for="list in lists"
			:key="list.key"
			:label="list.label"
			:data-results="list.key"
		>
			<ItemListRow
				v-for="(hit, index) in list.hits"
				:key="[hit.prefix, hit.pane.key, hit.block, hit.fieldname, hit.label].join('/')"
				as="button"
				type="button"
				class="text-left"
				:active="active === list.offset + index"
				@mousemove="active = list.offset + index"
				@click="emit('pick', hit)"
			>
				<template #prefix>
					<Icon :name="hit.pane.icon" class="text-ink-gray-6" />
				</template>
				<span class="block truncate text-ink-gray-8">{{ hit.label }}</span>
				<span class="mt-0.5 block truncate text-sm text-ink-gray-5">{{ hit.where }}</span>
			</ItemListRow>
		</SettingsNavGroup>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ItemListRow, SettingsNavGroup, TextInput } from "frappe-ui";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import type { SettingsHit, SettingsSearch } from "./settingsSearch";

const props = defineProps<{ search?: SettingsSearch }>();
const emit = defineEmits<{ pick: [hit: SettingsHit] }>();
const query = defineModel<string>({ required: true });

const results = computed(() => props.search?.find(query.value) ?? { own: [], other: [] });
const hits = computed(() => [...results.value.own, ...results.value.other]);
const lists = computed(() =>
	[
		{ key: "own", label: undefined, hits: results.value.own, offset: 0 },
		{
			key: "other",
			label: __("In other apps"),
			hits: results.value.other,
			offset: results.value.own.length,
		},
	].filter((list) => list.hits.length)
);

const active = ref(0);
watch(query, () => (active.value = 0));

const input = ref<InstanceType<typeof TextInput> | null>(null);
const list = ref<HTMLElement | null>(null);

function clear() {
	query.value = "";
	input.value?.focus();
}

async function move(by: number) {
	if (!hits.value.length) return;
	active.value = (active.value + by + hits.value.length) % hits.value.length;
	await nextTick();
	list.value?.querySelector("[data-state='active']")?.scrollIntoView({ block: "nearest" });
}
</script>
