<template>
	<HoverCard side="bottom" align="end" :hoverDelay="150">
		<template #trigger>
			<button class="flex text-ink-gray-5 hover:text-ink-gray-8" @click="openRouterScript">
				<LucideBraces class="h-3.5 w-3.5" />
			</button>
		</template>
		<div class="flex w-60 flex-col gap-1 p-3">
			<div class="text-sm font-medium text-ink-gray-8">Router script</div>
			<p class="text-p-sm text-ink-gray-6">
				Add navigation guards, redirect old paths, track page views and more.
			</p>
		</div>
	</HoverCard>
</template>

<script setup lang="ts">
import { HoverCard } from "frappe-ui"
import LucideBraces from "~icons/lucide/braces"
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()

const openRouterScript = () => (store.showRouterEditor = true)
</script>
