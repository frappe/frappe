<!-- The record's tab strip over one tab body. A body stays mounted, hidden, after its first
     visit, and scrolls on its own, so scroll and focus survive a switch on every tab. -->
<template>
	<div class="flex h-full min-h-0 flex-col" data-record-tabs>
		<div
			v-if="!ready"
			class="flex shrink-0 items-center gap-5 border-b px-[--page-gutter] py-2"
			data-record-tabs-skeleton
		>
			<div
				v-for="n in 4"
				:key="n"
				class="h-4 w-16 animate-pulse rounded-4 bg-surface-gray-2"
			/>
		</div>
		<Tabs
			v-else-if="strip.length"
			class="shrink-0 px-[--page-gutter]"
			:modelValue="active"
			:tabs="strip"
			@update:modelValue="emit('select', String($event))"
		/>

		<div
			v-for="entry in mounted"
			v-show="entry.item.name === active"
			:key="entry.item.name"
			class="min-h-0 flex-1 overflow-y-auto"
			:data-record-tab="entry.item.name"
		>
			<component
				:is="entry.item.component"
				v-if="entry.item.component"
				v-bind="{ ...entry.item.props, page }"
			/>
			<slot v-else-if="entry.item.name === DETAILS_TAB" name="details" />
			<p v-else class="py-10 text-center text-base text-ink-gray-5">
				{{ __("Nothing here yet.") }}
			</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import { Tabs } from "frappe-ui";
import type { ResolvedItem } from "@/recordPage/surface";
import type { RecordPageApi, TabItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import { DETAILS_TAB } from "./recordTabs";

const props = defineProps<{
	tabs: ResolvedItem<TabItem>[];
	active: string;
	ready: boolean;
	page: RecordPageApi;
}>();

const emit = defineEmits<{ select: [name: string] }>();

const visited = reactive(new Set<string>());

// `iconLeft`: frappe-ui draws a tab with `icon` and a label as an icon alone.
const strip = computed(() =>
	props.tabs
		.filter((entry) => !entry.hidden)
		.map(({ item }) => ({ value: item.name, label: item.label, iconLeft: item.icon }))
);

// A tab a script hides keeps its body, as a switch does.
const mounted = computed(() => props.tabs.filter((entry) => visited.has(entry.item.name)));

watch(
	() => props.active,
	(name) => name && visited.add(name),
	{ immediate: true }
);
</script>
