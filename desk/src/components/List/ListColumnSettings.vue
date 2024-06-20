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
			<div class="borderborder-gray-100 my-2 w-[15rem] rounded-lg bg-white p-1.5 shadow-xl">
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
							:body-classes="'w-[14rem]'"
							:options="fields"
							@update:modelValue="(e) => addColumn(e)"
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
							v-model="column.label"
							class="w-full"
						/>
						<FormControl
							type="text"
							size="md"
							:label="'Width'"
							class="w-full"
							v-model="column.width"
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
							@click="cancelUpdate(column.key)"
						/>
						<Button
							variant="solid"
							:label="'Update'"
							class="w-full flex-1"
							@click="updateColumn(column)"
						/>
					</div>
				</div>
			</div>
		</template>
	</NestedPopover>
</template>

<script setup>
import { computed, ref, watch, getCurrentInstance } from "vue"
import { Autocomplete, call } from "frappe-ui"
import Draggable from "vuedraggable"

import { isDefaultConfig, isDefaultOverriden, configName } from "@/stores/view"
import NestedPopover from "frappe-ui/src/components/ListFilter/NestedPopover.vue"

import IconReset from "@/components/Icons/IconReset.vue"

const instance = getCurrentInstance()

const props = defineProps({
	allColumns: {
		type: Array,
		default: [],
	},
})

const fields = computed(() => {
	let allFields = props.allColumns
	if (!allFields) return []

	return allFields.filter((field) => {
		return !columns.value.find((column) => column.key === field.value)
	})
})

const columns = defineModel()
const oldColumns = ref({})

watch(
	columns.value,
	(cols) => {
		if (!cols) return
		oldColumns.value = JSON.parse(JSON.stringify(cols))
	},
	{ once: true, immediate: true }
)

const resetToDefault = async (close) => {
	await call("frappe.desk.doctype.view_config.view_config.reset_default_config", {
		config_name: configName.value,
	})
	instance.parent.emit("reload")
	close()
}

function addColumn(c) {
	let _column = {
		label: c.label,
		type: c.type,
		key: c.value,
		width: "10rem",
		options: c.options,
	}
	columns.value.push(_column)
	instance.parent.emit("fetch")
}

function removeColumn(c) {
	columns.value = columns.value.filter((column) => column.key !== c.key)
}

const edit = ref(false)
const column = ref({
	label: "",
	key: "",
	width: "10rem",
})
const editColumn = (c) => {
	edit.value = true
	column.value = { ...c }
}

const updateColumn = (c) => {
	edit.value = false
	let index = columns.value.findIndex((column) => column.key === c.key)
	columns.value[index].label = c.label
	columns.value[index].width = c.width
}

const cancelUpdate = (key) => {
	edit.value = false
	let index = columns.value.findIndex((column) => column.key === key)
	column.value.label = columns.value[index].label
	column.value.width = columns.value[index].width
}
</script>
