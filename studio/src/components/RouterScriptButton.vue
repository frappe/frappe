<template>
	<IconButton
		v-if="store.hasRouterScript"
		:icon="LucideBraces"
		label="Router"
		tooltipPlacement="bottom"
		@click="openRouterScript"
	/>
	<HoverCard v-else side="bottom" align="end" :hoverDelay="150">
		<template #trigger>
			<button class="relative flex text-ink-gray-4 hover:text-ink-gray-8" @click="openRouterScript">
				<LucideBraces class="h-4 w-4" />
				<LucidePlus class="absolute -bottom-1 -right-1 h-2.5 w-2.5 rounded-full bg-surface-base" />
			</button>
		</template>
		<div class="flex w-60 flex-col gap-2 p-3 text-ink-gray-8">
			<div class="text-base font-semibold">Need more control?</div>
			<ul class="list-disc space-y-1 pl-4 text-sm text-ink-gray-6">
				<li>Add navigation guards</li>
				<li>Redirect old paths</li>
				<li>Track page views</li>
			</ul>
			<Button variant="subtle" class="mt-1 w-full" @click="openRouterScript">
				<template #prefix><LucidePlus class="h-4 w-4" /></template>
				Add router script
			</Button>
		</div>
	</HoverCard>
</template>

<script setup lang="ts">
import { Button, HoverCard } from "frappe-ui"
import IconButton from "@/components/IconButton.vue"
import LucidePlus from "~icons/lucide/plus"
import LucideBraces from "~icons/lucide/braces"
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()

const openRouterScript = () => (store.showRouterEditor = true)
</script>
