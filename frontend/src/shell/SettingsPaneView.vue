<!-- One pane: its header, then its blocks as the registered blocks component draws them. An
     addressed block or a search pick is scrolled to and flashed once the pane's bindings have loaded. -->
<template>
	<SettingsHeader>
		<div ref="title" class="relative isolate flex min-w-0 flex-col gap-1">
			<span data-flash aria-hidden="true" :class="TITLE_FLASH" />
			<h2 class="text-lg font-semibold text-ink-gray-8">{{ __(pane.label) }}</h2>
			<p v-if="pane.description" class="text-base text-ink-gray-6">
				{{ __(pane.description) }}
			</p>
		</div>
	</SettingsHeader>
	<div ref="root" class="contents">
		<component :is="blocks" :pane="pane" :reveal="revealing" @loaded="loaded = true" />
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch, type Component } from "vue";
import { SettingsHeader } from "frappe-ui";
import { __ } from "@/i18n";
import type { SettingsPane } from "./settingsPanes";
import type { SettingsHit } from "./settingsSearch";

interface Target {
	block?: string;
	fieldname?: string;
}

const props = defineProps<{
	pane: SettingsPane;
	/** The component `main.ts` registered to draw the blocks. */
	blocks: Component;
	/** The block the address names; it is scrolled to and flashed when the address changes to it. */
	block?: string;
	/** A search pick in this pane; a pane pick flashes the title. */
	reveal?: SettingsHit;
}>();

const TITLE_FLASH =
	"pointer-events-none absolute -inset-x-3 -inset-y-2 -z-10 rounded-4 bg-surface-gray-3 opacity-0";

const title = ref<HTMLElement | null>(null);
const root = ref<HTMLElement | null>(null);
const loaded = ref(false);
/** The pick the blocks component shows the tab of. */
const revealing = shallowRef<Target>();

const target = computed<Target | undefined>(
	() => props.reveal ?? (props.block ? { block: props.block } : undefined)
);

watch(
	() => [target.value, loaded.value] as const,
	async ([shown, ready]) => {
		if (!shown || !ready) return;
		if (!shown.block) return flash(title.value);
		revealing.value = shown;
		await nextTick();
		const section = root.value?.querySelector<HTMLElement>(
			`[data-block="${CSS.escape(shown.block)}"]`
		);
		const row = shown.fieldname
			? section?.querySelector<HTMLElement>(
					`[data-fieldname="${CSS.escape(shown.fieldname)}"]`
			  )
			: null;
		if (row) row.scrollIntoView({ block: "center", behavior: "smooth" });
		else section?.scrollIntoView({ block: "start", behavior: "smooth" });
		flash(row ?? section);
	},
	{ immediate: true }
);

function flash(element: HTMLElement | null | undefined) {
	element
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
}
</script>
