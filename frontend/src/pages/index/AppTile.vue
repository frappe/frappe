<!-- One app on the index: its logo and title, a link to where the app opens. A selection draws like a hover. -->
<template>
	<a
		:id="id"
		:href="app.route"
		role="option"
		:aria-selected="selected"
		class="group flex flex-col items-center gap-2 rounded-5 p-2 outline-none transition hover:bg-surface-gray-2 focus-visible:focus-ring"
		:class="{ 'bg-surface-gray-2': selected }"
		:data-app="app.app"
		:data-selected="selected || undefined"
	>
		<AppLogo
			:logo="app.logo"
			:title="app.title"
			class="transition group-hover:scale-[1.04]"
			:class="{ 'scale-[1.04]': selected }"
		/>
		<span
			class="line-clamp-2 text-center text-sm leading-snug text-ink-gray-8"
			:title="app.title"
		>
			{{ app.title }}
		</span>
	</a>
</template>

<script setup lang="ts">
import type { IndexApp } from "./apps";
import AppLogo from "./AppLogo.vue";

defineProps<{ id: string; app: IndexApp; selected: boolean }>();
</script>
