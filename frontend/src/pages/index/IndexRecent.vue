<!-- The index's Recent: one row per visited list or record, its app's logo, title, kind and when. -->
<template>
	<section class="mt-10 w-full" aria-labelledby="index-recent-title" data-index-recent>
		<h2 id="index-recent-title" class="mb-2 text-sm font-medium text-ink-gray-5">
			{{ __("Recent") }}
		</h2>
		<ul :id="id" role="listbox" aria-labelledby="index-recent-title" class="flex flex-col">
			<li v-for="row in rows" :key="row.key" role="none">
				<ItemListRow
					:id="selectableId(row.key)"
					as="a"
					size="lg"
					:href="row.visit.route"
					role="option"
					:aria-selected="row.selected"
					class="outline-none hover:bg-surface-gray-2 focus-visible:focus-ring"
					:class="{ 'bg-surface-gray-2': row.selected }"
					:data-recent="row.key"
					:data-selected="row.selected || undefined"
				>
					<template #prefix>
						<AppLogo
							:logo="row.visit.app_logo"
							:title="row.visit.app_title"
							:size="20"
						/>
					</template>
					<span class="flex min-w-0 items-baseline gap-2">
						<span class="truncate text-ink-gray-8" :title="row.visit.title">
							{{ row.visit.title }}
						</span>
						<span v-if="row.visit.kind" class="shrink-0 text-sm text-ink-gray-5">
							{{ row.visit.kind }}
						</span>
					</span>
					<template #suffix>
						<span class="text-sm text-ink-gray-5">{{ row.when }}</span>
					</template>
				</ItemListRow>
			</li>
		</ul>
	</section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ItemListRow, dayjs } from "frappe-ui";
import { __ } from "@/i18n";
import AppLogo from "./AppLogo.vue";
import { recentKey, type IndexVisit } from "./recent";
import { selectableId, type Selection } from "./selection";

const props = defineProps<{
	id: string;
	recent: IndexVisit[];
	selection: Selection;
	/** The site's time zone, which `visited` is written in. */
	siteZone: string;
}>();

const rows = computed(() =>
	props.recent.map((visit, position) => {
		const key = recentKey(position);
		return {
			visit,
			key,
			selected: props.selection.isSelected(key),
			when: dayjs.tz(visit.visited, props.siteZone).fromNow(),
		};
	})
);
</script>
