<template>
	<div v-if="sort" class="flex rounded">
		<Tooltip :text="sort[1]" :hover-delay="0.5">
			<div>
				<Button
					class="w-full rounded-none rounded-l border bg-gray-100 p-1.5"
					@click="toggleSortOrder"
				>
					<template #icon>
						<Icon
							:name="sort[1] == 'ASC' ? 'sort-ascending' : 'sort-descending'"
							class="h-3.5 w-3.5"
						>
						</Icon>
					</template>
				</Button>
			</div>
		</Tooltip>
		<Dropdown :options="sortOptions">
			<template v-slot="{ open }">
				<Button
					variant="ghost"
					class="flex items-center justify-between gap-1 rounded-l-none border border border-l-0 hover:bg-inherit"
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

<script setup>
import { computed, defineModel, getCurrentInstance } from "vue"
import { Button } from "frappe-ui"
import { Dropdown, FeatherIcon, Tooltip } from "frappe-ui"

const sort = defineModel()

const props = defineProps({
	allSortableFields: {
		type: Array,
		default: [],
	},
})

const sortField = computed(() => {
	const field = props.allSortableFields.find((field) => field.key === sort.value[0])
	return field ? field.label : ""
})

const sortOptions = computed(() => {
	return props.allSortableFields.map((field) => {
		return {
			label: field.label,
			onClick: () => {
				sort.value[0] = field.key
				instance.parent.emit("update")
			},
		}
	})
})

const instance = getCurrentInstance()

const toggleSortOrder = () => {
	sort.value[1] = sort.value[1] == "ASC" ? "DESC" : "ASC"
	instance.parent.emit("update")
}
</script>
