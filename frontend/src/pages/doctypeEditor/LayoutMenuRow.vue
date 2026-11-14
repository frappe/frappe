<!-- One row of the layout menu: icon, name, a gray badge and room for the open one's check. -->
<template>
	<ItemListRow
		as="button"
		type="button"
		class="text-left hover:bg-surface-gray-2 focus-visible:bg-surface-gray-2 focus-visible:outline-none"
		:class="{ '!pl-8': indented }"
	>
		<template v-if="icon" #prefix>
			<Icon :name="icon" class="size-4 text-ink-gray-6" />
		</template>
		<span
			class="block truncate"
			:class="indented ? 'text-ink-gray-7' : 'text-ink-gray-8'"
			:title="name"
			>{{ name }}</span
		>
		<template v-if="badge !== undefined" #suffix>
			<span class="flex items-center gap-2">
				<Badge :label="badge" theme="gray" />
				<span class="grid size-4 place-items-center" aria-hidden="true">
					<Icon
						v-if="open"
						name="lucide-check"
						class="size-4 text-ink-gray-7"
						data-layout-open
					/>
				</span>
			</span>
		</template>
	</ItemListRow>
</template>

<script setup lang="ts">
import { Badge, Icon, ItemListRow } from "frappe-ui";

defineProps<{ name: string; icon?: string; badge?: string; open?: boolean; indented?: boolean }>();
</script>
