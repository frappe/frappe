<!-- The quick app switcher: a centred row of app logos, the selected one on a gray plate. Keys are in `appSwitcherKey.ts`. -->
<template>
	<div
		class="fixed inset-0 z-[60] flex items-center justify-center p-4"
		@pointerdown.self="appSwitcher.cancel()"
	>
		<div
			role="listbox"
			:aria-label="__('Switch app')"
			class="flex max-w-full flex-wrap justify-center gap-1 rounded-6 bg-surface-modal p-2 shadow-2xl ring-1 ring-outline-gray-2"
		>
			<button
				v-for="(app, index) in appSwitcher.apps.value"
				:key="app.app"
				type="button"
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
import AppLogo from "./AppLogo.vue";
import { appSwitcher } from "./appSwitcher";
</script>
