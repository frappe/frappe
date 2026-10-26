<!-- One pane: its header, then each block's header over a skeleton of its rows. An addressed
     block is scrolled to and flashed. -->
<template>
	<SettingsHeader
		:title="__(pane.label)"
		:description="pane.description && __(pane.description)"
	/>
	<SettingsBody>
		<LoadingStatus />
		<section
			v-for="block in pane.blocks"
			:key="block.key"
			ref="sections"
			:data-block="block.key"
			class="relative isolate mt-8 scroll-mt-5 first:mt-5"
		>
			<span data-flash aria-hidden="true" :class="FLASH" />
			<h3 v-if="block.label" class="text-base font-semibold text-ink-gray-8">
				{{ __(block.label) }}
			</h3>
			<p v-if="block.description" class="mt-0.5 text-sm text-ink-gray-5">
				{{ __(block.description) }}
			</p>
			<div
				v-for="row in skeletonRows(block)"
				:key="row"
				class="flex items-center gap-8 border-b border-outline-gray-1 py-3.5 last:border-b-0"
			>
				<Skeleton class="h-4 w-36 rounded-1" />
				<Skeleton class="ml-auto h-7 w-56 rounded-4" />
			</div>
		</section>
	</SettingsBody>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { SettingsBody, SettingsHeader, Skeleton } from "frappe-ui";
import { __ } from "@/i18n";
import LoadingStatus from "./LoadingStatus.vue";
import type { SettingsBlock, SettingsPane } from "./settingsPanes";

const props = defineProps<{
	pane: SettingsPane;
	/** The block the address names; it is scrolled to and flashed when the address changes to it. */
	block?: string;
}>();

/** A rounded gray layer a little wider than the block, behind its content. */
const FLASH =
	"pointer-events-none absolute -inset-x-3 -inset-y-2 -z-10 rounded-4 bg-surface-gray-3 opacity-0";

const MOST_ROWS = 6;

const sections = ref<HTMLElement[]>([]);

/** As many rows as a field list names, up to `MOST_ROWS`; a whole layout or a component shows three. */
function skeletonRows(block: SettingsBlock): number {
	return Math.min(block.fields?.length || 3, MOST_ROWS);
}

watch(
	() => props.block,
	async (key) => {
		if (!key) return;
		await nextTick();
		const section = sections.value.find((element) => element.dataset.block === key);
		section?.scrollIntoView({ block: "start", behavior: "smooth" });
		section
			?.querySelector(":scope > [data-flash]")
			?.animate(
				[
					{ opacity: 0 },
					{ opacity: 1, offset: 0.1 },
					{ opacity: 1, offset: 0.6 },
					{ opacity: 0 },
				],
				{ duration: 2000, easing: "ease-out" }
			);
	},
	{ immediate: true }
);
</script>
