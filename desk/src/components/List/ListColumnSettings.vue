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
									<Icon name="es-line-drag" class="h-2.5 w-2.5 text-gray-600" />
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
								<svg
									width="16"
									height="16"
									viewBox="0 0 16 16"
									fill="none"
									xmlns="http://www.w3.org/2000/svg"
									class="h-4"
								>
									<path
										d="M2.35619 8.42909C2.35644 9.77009 2.84031 11.066 3.719 12.079C4.5977 13.092 5.81226 13.7542 7.13977 13.9439C8.46729 14.1336 9.8187 13.8382 10.946 13.1119C12.0732 12.3856 12.9008 11.2771 13.2766 9.98982C13.6525 8.70258 13.5515 7.32295 12.9922 6.10414C12.4329 4.88534 11.4528 3.90914 10.2318 3.35469C9.0108 2.80025 7.63079 2.70476 6.34504 3.08576C5.0593 3.46675 3.95409 4.29867 3.23226 5.42883"
										stroke="currentColor"
										stroke-linecap="round"
										stroke-linejoin="round"
									></path>
									<path
										d="M3.21297 2V5.42886H6.64183"
										stroke="currentColor"
										stroke-linecap="round"
										stroke-linejoin="round"
									></path>
								</svg>
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
import { isEqual } from "lodash"
import { config_settings, isDefaultConfig } from "@/stores/view"
import { Autocomplete, FeatherIcon, FormControl, call } from "frappe-ui"
import { computed, ref, watch, getCurrentInstance } from "vue"
import NestedPopover from "@/components/controls/NestedPopover.vue"
import Draggable from "vuedraggable"

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

// Reset Column Changes

const oldColumns = ref({})

watch(
	columns.value,
	(cols) => {
		if (!cols) return
		oldColumns.value = JSON.parse(JSON.stringify(cols))
	},
	{ once: true, immediate: true }
)

const columnsUpdated = computed(() => !isEqual(columns.value, oldColumns.value))

const resetToDefault = async (close) => {
	await call("frappe.desk.doctype.view_config.view_config.reset_default_config", {
		doctype: config_name.value,
	})
	instance.parent.emit("reload")
	close()
}

// Add / Remove Columns

function addColumn(c) {
	let _column = {
		label: c.label,
		type: c.type,
		key: c.value,
		width: "10rem",
		options: c.options,
	}
	columns.value.push(_column)
	instance.parent.emit("update")
}

function removeColumn(c) {
	columns.value = columns.value.filter((column) => column.key !== c.key)
}

// Edit Columns

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

watch(
	() => columnsUpdated.value,
	() => {
		if (isDefaultConfig.value && columnsUpdated.value) {
			instance.parent.emit("updateDefaultConfig")
		}
	},
	{ immediate: true }
)
</script>
