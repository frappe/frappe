<template>
	<div v-if="sort" class="flex">
		<Tooltip :text="sort[1] == 'ASC' ? 'ascending' : 'descending'" :hover-delay="0.5">
			<Button
				class="w-full rounded-none rounded-l border bg-gray-100 p-1.5"
				@click="toggleSortOrder"
			>
				<template #icon>
					<Icon :name="sort[1] == 'ASC' ? 'sort-ascending' : 'sort-descending'" class="h-3.5 w-3.5">
					</Icon>
				</template>
			</Button>
		</Tooltip>
		<Dropdown :options="sortOptions">
			<template v-slot="{ open }">
				<Button
					variant="subtle"
					class="flex items-center justify-between gap-1 rounded-l-none border border-l-0"
				>
					<div class="truncate">{{ sortField }}</div>
					<template #suffix>
						<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-4 w-4" />
					</template>
				</Button>
			</template>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { computed, defineModel, inject } from "vue"

import { Dropdown, Tooltip } from "frappe-ui"

import { fetchListFnKey } from "@/types/injectionKeys"
import { ListColumn, ListSort } from "@/types/list"

const fetchList = inject(fetchListFnKey, async () => {})

const props = defineProps<{
	allSortableFields: ListColumn[]
}>()

const sort = defineModel<ListSort>({ required: true })

const sortField = computed(() => {
	const field = props.allSortableFields.find((field) => field.key === sort.value[0])
	return field ? field.label : ""
})

const sortOptions = computed(() => {
	return props.allSortableFields.map((field) => {
		return {
			label: field.label,
			onClick: async () => {
				sort.value[0] = field.key
				await fetchList()
			},
		}
	})
})

const toggleSortOrder = async () => {
	sort.value[1] = sort.value[1] == "ASC" ? "DESC" : "ASC"
	await fetchList()
}
</script>
