<template>
	<div class="flex select-none flex-col pb-16">
		<div class="flex flex-col gap-3">
			<!-- inputs -->
			<div class="flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Inputs</h3>
				<Autocomplete
					:options="fieldTypeOptions"
					@update:modelValue="(option: SelectOption) => showAddInputPopover(option.value)"
					class="!w-auto"
				>
					<template #target="{ togglePopover }">
						<Button @click="togglePopover" size="sm" variant="ghost" icon="plus" />
					</template>
				</Autocomplete>
			</div>

			<div class="mb-4 flex flex-col gap-1" v-if="componentInputs.length > 0">
				<Popover
					v-for="(input, index) in componentInputs"
					:key="input.input_name"
					:show="showEditPopover && editingIndex === index"
					@update:show="
						(show: boolean) => {
							if (!show) cancelEdit()
						}
					"
					placement="bottom-start"
				>
					<template #target>
						<div
							class="group flex flex-1 cursor-pointer justify-between rounded border border-gray-300 px-2 py-1 hover:bg-gray-50"
							@click="editInput(input, index)"
						>
							<div class="flex items-center gap-2">
								<FeatherIcon :name="getFieldTypeIcon(input.type)" class="h-4 w-4 text-gray-500" />
								<span class="text-sm text-gray-800">{{ input.input_name }}</span>
							</div>
							<button
								class="flex cursor-pointer items-center rounded-sm p-1 text-gray-700 opacity-0 transition-opacity hover:text-gray-900 group-hover:opacity-100"
								@click.stop="componentEditorStore.removeComponentInput(index)"
							>
								<FeatherIcon name="x" class="h-4 w-4" />
							</button>
						</div>
					</template>
					<template #body-main>
						<div
							class="w-64 space-y-4 p-4"
							v-if="editingInput && editingIndex === index"
							@keydown.enter="saveInput"
						>
							<FormControl
								type="text"
								label="Name"
								v-model="editingInput.input_name"
								placeholder="e.g. user_name"
								autocomplete="off"
								:required="true"
							/>
							<FormControl
								type="autocomplete"
								label="Type"
								:options="fieldTypeOptions"
								:modelValue="
									editingInput ? fieldTypeOptions.find((opt) => opt.value === editingInput!.type) : null
								"
								@update:modelValue="
									(option: SelectOption) => {
										if (editingInput) {
											editingInput.type = option.value
											setInputControl()
										}
									}
								"
								:required="true"
							>
								<template #prefix>
									<FeatherIcon
										:name="editingInput ? getFieldTypeIcon(editingInput.type) : 'help-circle'"
										class="mr-1 h-3 w-3 text-gray-500"
									/>
								</template>
								<template #item-prefix="{ option }">
									<FeatherIcon :name="getFieldTypeIcon(option.value)" class="h-3 w-3 text-gray-500" />
								</template>
							</FormControl>
							<FormControl
								v-if="editingInput.type === 'select'"
								type="textarea"
								label="Options"
								v-model="editingInput.options"
								:required="true"
								placeholder="Enter list of options, each on a new line"
							/>

							<!-- Default value -->
							<component
								:is="editingInput.inputControl"
								:type="editingInput.inputType"
								label="Default Value"
								v-model="editingInput.default"
							/>
							<FormControl
								type="textarea"
								label="Description"
								v-model="editingInput.description"
								placeholder="Enter description (optional)"
							/>
							<FormControl
								type="checkbox"
								label="Is Required"
								size="sm"
								v-model="editingInput.required"
								class="[&>label]:text-sm [&>label]:text-ink-gray-5"
							/>
							<div class="flex gap-2">
								<Button variant="solid" @click="saveInput">Save</Button>
								<Button variant="outline" @click="cancelEdit">Cancel</Button>
							</div>
						</div>
					</template>
				</Popover>
			</div>

			<EmptyState v-else message="No inputs added" />

			<!-- Test Inputs -->
			<div class="flex items-center justify-between text-sm font-medium">
				<h3 class="cursor-pointer text-base text-gray-900">Test Inputs</h3>
			</div>
			<PropsEditor
				v-if="componentEditorStore.studioComponentBlock"
				:block="componentEditorStore.studioComponentBlock"
				:isEditingComponent="true"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, markRaw, computed } from "vue"
import { Autocomplete, Popover, FormControl } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import type { SelectOption } from "@/types"
import type { ComponentInput } from "@/types/Studio/StudioComponent"
import Code from "@/components/Code.vue"
import ColorPicker from "@/components/ColorPicker.vue"
import PropsEditor from "@/components/PropsEditor.vue"
import useComponentEditorStore from "@/stores/componentEditorStore"

const componentEditorStore = useComponentEditorStore()
const componentInputs = computed(() => componentEditorStore.componentInputs)
const showEditPopover = ref(false)
const editingInput = ref<ComponentInput | null>(null)
const editingIndex = ref<number>(-1)

const fieldTypeOptions = [
	{ label: "Text", value: "text" },
	{ label: "Number", value: "number" },
	{ label: "Checkbox", value: "checkbox" },
	{ label: "Textarea", value: "textarea" },
	{ label: "Select", value: "select" },
	{ label: "Code", value: "code" },
	{ label: "Color", value: "color" },
]

const getFieldTypeIcon = (type: string) => {
	const iconMap: Record<string, string> = {
		text: "type",
		number: "hash",
		checkbox: "check-square",
		textarea: "align-left",
		select: "list",
		code: "code",
		color: "droplet",
	}
	return iconMap[type] || "type"
}

const editInput = (input: ComponentInput, index: number) => {
	editingInput.value = { ...input }
	editingIndex.value = index
	setInputControl()
	showEditPopover.value = true
}

const saveInput = () => {
	if (editingInput.value && editingIndex.value >= 0) {
		componentEditorStore.updateComponentInput(editingIndex.value, editingInput.value)
	}
	showEditPopover.value = false
	editingInput.value = null
	editingIndex.value = -1
}

const cancelEdit = () => {
	showEditPopover.value = false
	editingInput.value = null
	editingIndex.value = -1
}

const showAddInputPopover = (fieldType: string) => {
	const fieldTypeLabel = fieldTypeOptions.find((opt) => opt.value === fieldType)?.label || fieldType
	const newInputData: ComponentInput = {
		input_name: fieldTypeLabel,
		type: fieldType,
		description: "",
		default: "",
	}
	componentEditorStore.addComponentInput(newInputData)
	const newIndex = componentInputs.value.length - 1
	setTimeout(() => {
		editInput(newInputData, newIndex)
	}, 10) // Small delay to ensure DOM is updated
}

const setInputControl = () => {
	if (!editingInput.value) return
	if (editingInput.value.type === "code") {
		editingInput.value.inputControl = markRaw(Code)
	} else if (editingInput.value.type === "color") {
		editingInput.value.inputControl = markRaw(ColorPicker)
	} else {
		editingInput.value.inputControl = "FormControl"
		editingInput.value.inputType = editingInput.value?.type === "textarea" ? "textarea" : "text"
	}
}
</script>
