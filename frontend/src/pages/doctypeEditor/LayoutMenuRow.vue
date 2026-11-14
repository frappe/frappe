<!-- One row of the layout menu: icon, name and, in the same right slot on every row, where its
     layout comes from. The open one has a gray fill. A conditional layout is a child row: a corner
     icon, its title, then its condition in gray. -->
<template>
	<ItemListRow
		as="button"
		type="button"
		class="text-left focus-visible:outline-none"
		:aria-current="open ? 'true' : undefined"
		:class="[
			open
				? 'bg-surface-gray-3'
				: danger
				? 'hover:bg-surface-red-2 focus-visible:bg-surface-red-2'
				: 'hover:bg-surface-gray-2 focus-visible:bg-surface-gray-2',
			{ '!pl-8': indented },
		]"
	>
		<template #prefix>
			<Icon
				:name="indented ? 'lucide-corner-down-right' : icon"
				class="size-4"
				:class="danger ? 'text-ink-red-7' : 'text-ink-gray-6'"
			/>
		</template>
		<span
			v-if="!condition"
			class="block truncate"
			:class="danger ? 'text-ink-red-7' : 'text-ink-gray-8'"
			:title="name"
			>{{ name }}</span
		>
		<span v-else class="flex min-w-0 items-baseline gap-1.5">
			<span class="block max-w-[60%] shrink-0 truncate text-ink-gray-8" :title="name">{{
				name
			}}</span>
			<Tooltip :text="condition">
				<span
					class="block min-w-0 truncate"
					:class="open ? 'text-ink-gray-7' : 'text-ink-gray-6'"
					data-layout-condition
					>{{ condition }}</span
				>
			</Tooltip>
		</span>
		<template v-if="source !== undefined" #suffix>
			<span
				class="text-sm leading-tighter"
				:class="open ? 'text-ink-gray-7' : 'text-ink-gray-6'"
				data-layout-source
				>{{ source }}</span
			>
		</template>
	</ItemListRow>
</template>

<script setup lang="ts">
import { Icon, ItemListRow, Tooltip } from "frappe-ui";

defineProps<{
	name: string;
	icon?: string;
	source?: string;
	condition?: string;
	open?: boolean;
	indented?: boolean;
	danger?: boolean;
}>();
</script>
