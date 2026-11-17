<template>
	<div class="flex items-center">
		<Button
			size="sm"
			variant="solid"
			:disabled="disabled"
			:loading="store.publishingPage || store.publishingApp"
			class="rounded-br-none rounded-tr-none border-0"
			@click="store.publishPage()"
		>
			{{
				store.publishingApp
					? "Publishing App..."
					: store.publishingPage
						? "Publishing Page..."
						: "Publish Page"
			}}
		</Button>
		<Dropdown
			:options="[
				{
					group: 'Revert',
					hideLabel: true,
					options: [
						{
							label: 'Revert Changes',
							icon: LucideRotateCcw,
							onClick: () => store.revertPage(),
							condition: () =>
								Boolean(store.activePage?.published) && Boolean(store.activePage?.draft_blocks),
						},
					],
				},
				{
					group: 'Publish',
					hideLabel: true,
					options: [
						{
							label: 'Publish App',
							icon: LucideGlobe,
							onClick: () => store.publishApp(),
						},
					],
				},
				{
					group: 'Unpublish',
					hideLabel: true,
					options: [
						{
							label: 'Unpublish Page',
							icon: LucideCircleDashed,
							onClick: () => store.unpublishPage(),
							condition: () => Boolean(store.activePage?.published),
						},
						{
							label: 'Unpublish App',
							icon: GlobeOff,
							onClick: () => store.unpublishApp(),
						},
					],
				},
			]"
			size="sm"
			align="end"
		>
			<template #default>
				<Button
					size="sm"
					variant="solid"
					:disabled="disabled"
					icon="lucide-chevron-down"
					class="!w-6 justify-start rounded-bl-none rounded-tl-none border-0 pr-0 text-xs"
					:class="{ 'pointer-events-none': isPublishing }"
					:tabindex="isPublishing ? -1 : undefined"
				/>
			</template>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Dropdown, Button } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import LucideCircleDashed from "~icons/lucide/circle-dashed"
import LucideGlobe from "~icons/lucide/globe"
import LucideRotateCcw from "~icons/lucide/rotate-ccw"
import GlobeOff from "@/components/Icons/GlobeOff.vue"

defineProps<{
	disabled?: boolean
}>()

const store = useStudioStore()
const isPublishing = computed(() => store.publishingPage || store.publishingApp)
</script>
