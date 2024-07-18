<template>
	<NestedPopover>
		<template #target>
			<Button label="Columns">
				<template #prefix>
					<FeatherIcon name="columns" class="h-3.5" />
				</template>
			</Button>
		</template>

		<template #body="{ close }">
			<div class="my-2 w-60 rounded-lg border border-gray-100 bg-white p-1.5 shadow-xl">
				<div v-if="!edit">
					<Draggable :list="columns" item-key="key">
						<template #item="{ element }">
							<div
								class="flex cursor-grab items-center justify-between gap-6 rounded px-2 py-1.5 text-base text-gray-800 hover:bg-gray-100"
							>
								<div class="flex items-center gap-2">
									<button><Icon name="drag-sm" class="h-3 w-3 text-gray-600" /></button>
									<div>{{ element.label }}</div>
								</div>
								<div class="flex cursor-pointer items-center gap-1">
									<Button variant="ghost" class="!h-5 w-5 !p-1" @click="editColumn(element)">
										<FeatherIcon name="edit" class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" class="!h-5 w-5 !p-1" @click="removeColumn(element)">
										<FeatherIcon name="x" class="h-3.5 w-3.5" />
									</Button>
								</div>
							</div>
						</template>
					</Draggable>

					<div class="mt-1.5 flex flex-col gap-1 border-t pt-1.5">
						<Autocomplete
							:body-classes="'w-56'"
							:options="fields"
							@update:modelValue="(field: ListField) => addColumn(field)"
						>
							<template #target="{ togglePopover }">
								<Button
									class="w-full !justify-start !text-gray-600"
									variant="ghost"
									@click="togglePopover()"
									:label="'Add Column'"
								>
									<template #prefix>
										<FeatherIcon name="plus" class="h-4" />
									</template>
								</Button>
							</template>
						</Autocomplete>
						<Button
							v-if="isDefaultConfig && isDefaultOverriden"
							class="w-full !justify-start !text-gray-600"
							variant="ghost"
							@click="resetToDefault(close)"
							label="Reset To Default"
						>
							<template #prefix>
								<IconReset class="h-3" />
							</template>
						</Button>
					</div>
				</div>

				<div
					v-else
					class="flex flex-col items-center justify-between gap-2 rounded px-2 py-1.5 text-base text-gray-800"
				>
					<div class="flex flex-col items-center gap-3">
						<FormControl
							type="text"
							size="md"
							:label="'Label'"
							v-model="activeColumn.label"
							class="w-full"
						/>
						<FormControl
							type="text"
							size="md"
							:label="'Width'"
							class="w-full"
							v-model="activeColumn.width"
							placeholder="10rem"
							:description="'Width can be in number, pixel or rem (eg. 3, 30px, 10rem)'"
							:debounce="500"
						/>
					</div>

					<div class="flex w-full gap-2 border-t pt-2">
						<Button
							variant="subtle"
							:label="'Cancel'"
							class="w-full flex-1"
							@click="cancelUpdate(activeColumn.key)"
						/>
						<Button
							variant="solid"
							:label="'Update'"
							class="w-full flex-1"
							@click="updateColumn(activeColumn)"
						/>
					</div>
				</div>
			</div>
		</template>
	</NestedPopover>
</template>

<script setup lang="ts">
import { computed, ref, watch, inject } from "vue"
import Draggable from "vuedraggable"

import { Autocomplete, NestedPopover, call } from "frappe-ui"
import IconReset from "@/components/Icons/IconReset.vue"

import { isDefaultConfig, isDefaultOverriden, configName } from "@/stores/view"
import { cloneObject } from "@/utils"

import { fetchListFnKey, renderListFnKey } from "@/types/injectionKeys"
import { ListField, ListColumn } from "@/types/list"

const fetchList = inject(fetchListFnKey, async () => {})
const renderList = inject(renderListFnKey, async () => {})

const props = defineProps<{
	allColumns: ListField[]
}>()

const columns = defineModel<ListColumn[]>({ required: true })
const oldColumns = ref<ListColumn[]>()

const fields = computed(() => {
	let allFields = props.allColumns
	if (!allFields) return []

	return allFields.filter((field) => {
		return !columns.value.find((column) => column.key === field.key)
	})
})

watch(
	columns.value,
	(cols) => {
		if (!cols) return
		oldColumns.value = cloneObject(cols)
	},
	{ once: true, immediate: true }
)

const resetToDefault = async (close: () => void) => {
	await call("frappe.desk.doctype.view_config.view_config.reset_default_config", {
		config_name: configName.value,
	})
	await renderList()
	close()
}

const addColumn = async (field: ListField): Promise<void> => {
	let _column: ListColumn = {
		...field,
		width: "10rem",
	}
	columns.value.push(_column)
	await fetchList()
}

function removeColumn(col: ListColumn) {
	columns.value = columns.value.filter((column) => column.key !== col.key)
}

const edit = ref(false)
const activeColumn = ref<ListColumn>({
	key: "",
	label: "",
	type: "Data",
	options: [],
	width: "10rem",
})

const editColumn = (col: ListColumn) => {
	edit.value = true
	activeColumn.value = { ...col }
}

const updateColumn = (col: ListColumn) => {
	edit.value = false
	let index = columns.value.findIndex((column) => column.key === col.key)
	columns.value[index].label = col.label
	columns.value[index].width = col.width
}

const cancelUpdate = (key: string) => {
	edit.value = false
	let index = columns.value.findIndex((column) => column.key === key)
	activeColumn.value.label = columns.value[index].label
	activeColumn.value.width = columns.value[index].width
}
</script>
