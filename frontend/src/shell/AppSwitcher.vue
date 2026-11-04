<!-- The quick app switcher: a centred row of app logos, the selected one on a gray plate. Keys are in `appSwitcherKey.ts`. -->
<template>
	<div
		class="fixed inset-0 z-[60] flex items-center justify-center p-4"
		role="dialog"
		aria-modal="true"
		:aria-label="__('Switch app')"
		@pointerdown.self="appSwitcher.cancel()"
	>
		<!-- The keys stay on the document; focus sits here so a screen reader follows the selection. -->
		<div
			ref="list"
			role="listbox"
			tabindex="-1"
			:aria-label="__('Switch app')"
			:aria-activedescendant="`app-switcher-${appSwitcher.selected.value}`"
			class="flex max-w-full outline-none flex-wrap justify-center gap-1 rounded-6 bg-surface-modal p-2 shadow-2xl ring-1 ring-outline-gray-2"
		>
			<button
				v-for="(app, index) in appSwitcher.apps.value"
				:id="`app-switcher-${index}`"
				:key="app.app"
				type="button"
				tabindex="-1"
				role="option"
				:aria-selected="index === appSwitcher.selected.value"
				:data-app="app.app"
				class="flex w-24 flex-col items-center gap-2 rounded-5 p-2 outline-none transition"
				:class="
					index === appSwitcher.selected.value
						? 'bg-surface-gray-3'
						: 'hover:bg-surface-gray-2'
				"
				@click="appSwitcher.choose(index)"
			>
				<span class="relative">
					<AppLogo :logo="app.logo" :title="app.title" />
					<span
						v-if="app.kind === 'link'"
						class="absolute -bottom-1 -right-1 flex size-5 items-center justify-center rounded-full bg-surface-white text-ink-gray-7 ring-1 ring-outline-gray-3"
						data-link-mark
						:title="__('Leaves the desk')"
					>
						<span class="lucide-arrow-up-right size-3" aria-hidden="true" />
						<span class="sr-only">{{ __("Leaves the desk") }}</span>
					</span>
				</span>
				<span
					class="w-full truncate text-center text-sm text-ink-gray-8"
					:title="app.title"
					>{{ app.title }}</span
				>
			</button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, useTemplateRef } from "vue";
import AppLogo from "./AppLogo.vue";
import { appSwitcher } from "./appSwitcher";

const list = useTemplateRef<HTMLElement>("list");
const before = document.activeElement as HTMLElement | null;

onMounted(() => list.value?.focus({ preventScroll: true }));
onBeforeUnmount(() => before?.focus({ preventScroll: true }));
</script>
