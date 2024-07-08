<template>
	<div v-if="titleField[0] == column.key" class="flex items-center">
		<Avatar
			class="mx-2"
			:image="row[titleField[1]]"
			size="md"
			shape="circle"
			v-if="row[titleField[1]] != ''"
		/>
		<span class="text-base">{{ item }}</span>
	</div>
	<div
		v-else-if="['modified', 'creation'].includes(column.key) && dayjs"
		class="text-sm font-semibold text-gray-500"
	>
		{{ dayjs().to(dayjs(item)) }}
	</div>
	<template v-else-if="column.key == 'enabled' || column.key == 'status'">
		<Badge
			v-if="item == '1' || item == '0'"
			:variant="'outline'"
			:theme="item ? 'green' : 'red'"
			size="md"
			:label="item ? 'Enabled' : 'Disabled'"
		></Badge>
		<Badge
			v-else
			:variant="'outline'"
			:theme="guessColour(item as string)"
			size="md"
			:label="item"
		></Badge>
	</template>
	<Badge
		v-else-if="column.key == 'disabled'"
		:variant="'outline'"
		:theme="item ? 'red' : 'green'"
		size="md"
		:label="item ? 'Disabled' : 'Enabled'"
	></Badge>
	<Checkbox
		v-else-if="column.type === 'Check'"
		class="mx-4 text-gray-800"
		size="sm"
		:model-value="Boolean(item)"
		:disabled="true"
	/>
	<Avatar
		v-else-if="['Image', 'Attach Image'].includes(column.type)"
		class="mt-1"
		:image="item"
		size="xl"
		shape="square"
	>
	</Avatar>
	<div v-else class="text-base" :class="column.type === 'Link' ? 'hover:underline' : ''">
		{{ item }}
	</div>
</template>

<script setup lang="ts">
import { inject } from "vue"
import { Badge, Checkbox, Avatar } from "frappe-ui"

import { guessColour } from "@/utils/list"

import { ListColumn, ListRow } from "@/types/list"

defineProps<{
	row: ListRow
	column: ListColumn
	item: string | number | boolean
	titleField: [string, string]
}>()

const dayjs = inject<any>("$dayjs")
</script>
