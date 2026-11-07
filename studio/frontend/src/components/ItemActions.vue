<template>
	<div
		class="invisible ml-auto flex items-center text-ink-gray-5 group-hover/item:visible has-[.active-item]:visible"
	>
		<button
			class="flex cursor-pointer items-center rounded-1 p-1 text-ink-gray-6 hover:bg-surface-gray-4"
			@click="$emit('edit')"
		>
			<span class="lucide-pencil size-3" />
		</button>
		<Dropdown :options="menuOptions">
			<template v-slot="{ open }">
				<button
					class="flex cursor-pointer items-center rounded-1 p-1 text-ink-gray-6 hover:bg-surface-gray-4"
					:class="open ? 'active-item' : ''"
				>
					<span class="lucide-ellipsis h-3 w-3" />
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
