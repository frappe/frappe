<template>
	<HoverCard side="bottom" align="end" :hoverDelay="150">
		<template #trigger>
			<button class="flex text-ink-gray-4 hover:text-ink-gray-8" @click="openRouterScript">
				<LucideBraces class="h-4 w-4" />
			</button>
		</template>
		<div class="flex w-60 flex-col gap-2 p-3 text-ink-gray-8">
			<div class="text-base font-semibold">Router script</div>
			<ul class="list-disc space-y-1 pl-4 text-sm text-ink-gray-6">
				<li>Add navigation guards</li>
				<li>Redirect old paths</li>
				<li>Track page views</li>
			</ul>
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
