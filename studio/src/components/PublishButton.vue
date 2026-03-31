<template>
	<div class="flex items-center">
		<Button
			size="sm"
			variant="solid"
			:disabled="disabled || publishingPage"
			:loading="publishingPage || publishingApp"
			class="rounded-br-none rounded-tr-none border-0"
			@click="
				() => {
					publishingPage = true
					store.publishPage().finally(() => (publishingPage = false))
				}
			"
		>
			{{ publishingApp ? "Publishing App..." : publishingPage ? "Publishing Page..." : "Publish Page" }}
		</Button>
		<Dropdown
			:options="[
				{
					label: 'Publish App',
					icon: 'globe',
					onClick: () => {
						publishingApp = true
						store.publishApp().finally(() => (publishingApp = false))
					},
				},
			]"
			size="sm"
			placement="right"
		>
			<template v-slot="{ open }">
				<Button
					size="sm"
					variant="solid"
					@click="open"
					:disabled="disabled || publishingPage || publishingApp"
					icon="chevron-down"
					class="!w-6 justify-start rounded-bl-none rounded-tl-none border-0 pr-0 text-xs"
				/>
			</template>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Dropdown } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"

defineProps<{
	disabled?: boolean
}>()

const store = useStudioStore()
const publishingPage = ref(false)
const publishingApp = ref(false)
</script>
