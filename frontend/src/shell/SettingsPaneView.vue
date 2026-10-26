<!-- One pane: its header, then its blocks as the registered blocks component draws them. An
     addressed block is scrolled to and flashed once the pane's bindings have loaded. -->
<template>
	<SettingsHeader
		:title="__(pane.label)"
		:description="pane.description && __(pane.description)"
	/>
	<div ref="root" class="contents">
		<component :is="blocks" :pane="pane" @loaded="loaded = true" />
	</div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch, type Component } from "vue";
import { SettingsHeader } from "frappe-ui";
import { __ } from "@/i18n";
import type { SettingsPane } from "./settingsPanes";

const props = defineProps<{
	pane: SettingsPane;
	/** The component `main.ts` registered to draw the blocks. */
	blocks: Component;
	/** The block the address names; it is scrolled to and flashed when the address changes to it. */
	block?: string;
}>();

const root = ref<HTMLElement | null>(null);
const loaded = ref(false);

watch(
	() => [props.block, loaded.value] as const,
	async ([key, ready]) => {
		if (!key || !ready) return;
		await nextTick();
		const section = root.value?.querySelector<HTMLElement>(
			`[data-block="${CSS.escape(key)}"]`
		);
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
