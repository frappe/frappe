<template>
	<div class="flex select-none flex-col pb-16">
		<div class="flex flex-col gap-3">
			<!-- inputs -->
			<SectionContainer title="Inputs">
				<template #actions>
					<Combobox
						:options="fieldTypeOptions"
						@update:modelValue="(value: string) => showAddInputPopover(value)"
						class="!w-auto"
					>
						<template #trigger>
							<Button size="sm" variant="ghost" icon="lucide-plus" />
						</template>
					</Combobox>
				</template>

				<div class="flex flex-col gap-1" v-if="componentInputs.length > 0">
					<Popover
						v-for="(input, index) in componentInputs"
						:key="input.input_name"
						:show="showEditPopover && editingIndex === index"
						@update:show="
							(show: boolean) => {
								if (!show) cancelEdit()
							}
						"
						placement="bottom-center"
					>
						<template #target>
							<div
								class="group flex flex-1 cursor-pointer justify-between rounded border border-outline-gray-2 px-2 py-1 hover:bg-surface-gray-1"
								@click="editInput(input, index)"
							>
								<div class="flex items-center gap-2">
									<FeatherIcon :name="getFieldTypeIcon(input.type)" class="h-4 w-4 text-ink-gray-4" />
									<span class="text-sm text-ink-gray-7">{{ input.input_name }}</span>
								</div>
								<button
									class="flex cursor-pointer items-center rounded-sm p-1 text-ink-gray-6 opacity-0 transition-opacity hover:text-ink-gray-8 group-hover:opacity-100"
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
								@keydown="handleInputKeydown"
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
									type="combobox"
									label="Type"
									:options="fieldTypeOptions"
									:modelValue="editingInput ? editingInput.type : null"
									@update:modelValue="
										(val: string) => {
											if (editingInput) {
												editingInput.type = val
												setInputControl()
											}
										}
									"
									:required="true"
								>
									<template #prefix>
										<FeatherIcon
											:name="editingInput ? getFieldTypeIcon(editingInput.type) : 'help-circle'"
											class="mr-1 h-3 w-3 text-ink-gray-4"
										/>
									</template>
									<template #item-prefix="{ item }">
										<FeatherIcon :name="getFieldTypeIcon(item.value)" class="h-3 w-3 text-ink-gray-4" />
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
								<div class="text-xs text-ink-gray-4">
									Press
									<kbd class="rounded bg-surface-gray-2 px-1 py-0.5">⌘</kbd>
									+
									<kbd class="rounded bg-surface-gray-2 px-1 py-0.5">S</kbd>
									to save
								</div>
							</div>
						</template>
					</Popover>
				</div>

				<EmptyState v-else message="No inputs added" />
			</SectionContainer>

			<!-- Test Inputs -->
			<SectionContainer title="Test Inputs">
				<PropsEditor
					v-if="componentEditorStore.studioComponentBlock"
					:block="componentEditorStore.studioComponentBlock"
					:isTestingComponent="true"
				/>
			</SectionContainer>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, markRaw, computed } from "vue"
import { Combobox, Popover, FormControl } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import type { SelectOption } from "@/types"
import type { ComponentInput } from "@/types/Studio/StudioComponent"
import Code from "@/components/Code.vue"
import ColorInput from "@/components/ColorInput.vue"
import PropsEditor from "@/components/PropsEditor.vue"
import useComponentEditorStore from "@/stores/componentEditorStore"
import { isCtrlOrCmd } from "@/utils/helpers"

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
		editingInput.value.inputControl = markRaw(ColorInput)
	} else {
		editingInput.value.inputControl = "FormControl"
		editingInput.value.inputType = editingInput.value?.type === "textarea" ? "textarea" : "text"
	}
}

const handleInputKeydown = (e: KeyboardEvent) => {
	if (isCtrlOrCmd(e) && e.key === "s") {
		e.preventDefault()
		saveInput()
	}
}
</script>
