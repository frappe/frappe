<template>
	<div
		class="invisible ml-auto flex items-center text-ink-gray-5 group-hover/item:visible has-[.active-item]:visible"
	>
		<button
			class="rounded-sm flex cursor-pointer items-center p-1 text-ink-gray-6 hover:bg-surface-gray-4"
			@click="$emit('edit')"
		>
			<LucidePencil class="size-3" />
		</button>
		<Dropdown :options="menuOptions" trigger="click">
			<template v-slot="{ open }">
				<button
					class="rounded-sm flex cursor-pointer items-center p-1 text-ink-gray-6 hover:bg-surface-gray-4"
					:class="open ? 'active-item' : ''"
				>
					<LucideEllipsis class="h-3 w-3" />
				</button>
			</template>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { Dropdown } from "frappe-ui"
import LucidePencil from "~icons/lucide/pencil"
import LucideEllipsis from "~icons/lucide/ellipsis"

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
