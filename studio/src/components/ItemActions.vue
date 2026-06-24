<template>
	<div
		class="invisible ml-auto flex items-center text-ink-gray-5 group-hover/item:visible has-[.active-item]:visible"
	>
		<button
			class="flex cursor-pointer items-center rounded-sm p-1 text-ink-gray-6 hover:bg-surface-gray-4"
			@click="$emit('edit')"
		>
			<FeatherIcon name="edit" class="size-3" />
		</button>
		<Dropdown :options="menuOptions" trigger="click">
			<template v-slot="{ open }">
				<button
					class="flex cursor-pointer items-center rounded-sm p-1 text-ink-gray-6 hover:bg-surface-gray-4"
					:class="open ? 'active-item' : ''"
				>
					<FeatherIcon name="more-horizontal" class="h-3 w-3" />
				</button>
			</template>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { Dropdown } from "frappe-ui"

defineProps<{
	menuOptions: Array<{
		label: string
		icon: string
		theme?: string
		onClick: () => void
	}>
}>()

defineEmits<{
	edit: []
}>()
</script>
