<!-- The dashed "Get more apps" tile after the apps: a link out to the Cloud Settings marketplace. -->
<template>
	<a
		:id="id"
		:href="href"
		role="option"
		:aria-selected="selected"
		class="group flex flex-col items-center gap-2 rounded-5 p-2 outline-none transition hover:bg-surface-gray-2 focus-visible:focus-ring"
		:class="{ 'bg-surface-gray-2': selected }"
		data-more-apps
		:data-selected="selected || undefined"
	>
		<span
			class="flex size-14 items-center justify-center rounded-[22%] border border-dashed border-outline-gray-3 text-ink-gray-5 transition group-hover:scale-[1.04]"
			:class="{ 'scale-[1.04]': selected }"
		>
			<span class="lucide-plus size-5" aria-hidden="true" />
		</span>
		<span class="line-clamp-2 text-center text-sm leading-snug text-ink-gray-6">
			{{ __("Get more apps") }}
		</span>
	</a>
</template>

<script setup lang="ts">
import { __ } from "@/i18n";

defineProps<{ id: string; href: string; selected: boolean }>();
</script>
