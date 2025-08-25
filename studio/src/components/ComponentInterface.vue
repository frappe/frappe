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

			<div class="mb-4 mt-3 flex flex-col gap-1" v-if="componentInputs.length > 0">
				<Popover
					v-for="(input, index) in componentInputs"
					:key="input.name"
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
							class="group flex flex-1 cursor-pointer items-center justify-between rounded-lg border border-transparent px-2 hover:border-gray-200 hover:bg-gray-50"
							@click="editInput(input, index)"
						>
							<div class="flex items-center gap-2">
								<FeatherIcon :name="getFieldTypeIcon(input.type)" class="h-4 w-4 text-gray-500" />
								<span class="text-sm font-medium text-gray-900">{{ input.name }}</span>
							</div>
							<Button
								variant="ghost"
								size="sm"
								icon="x"
								class="opacity-0 transition-opacity group-hover:opacity-100"
								@click.stop="removeInput(index)"
							/>
						</div>
					</template>
					<template #body-main>
						<div class="w-64 space-y-4 p-4" v-if="editingInput && editingIndex === index">
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Name</label>
								<TextInput v-model="editingInput.name" placeholder="Enter input name" />
							</div>
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Type</label>
								<Autocomplete
									:options="fieldTypeOptions"
									:modelValue="
										editingInput ? fieldTypeOptions.find((opt) => opt.value === editingInput!.type) : null
									"
									@update:modelValue="
										(option: SelectOption) => editingInput && (editingInput.type = option.value)
									"
								>
									<template #target="{ togglePopover }">
										<div
											@click="togglePopover"
											class="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 hover:bg-gray-50"
										>
											<FeatherIcon
												:name="editingInput ? getFieldTypeIcon(editingInput.type) : 'help-circle'"
												class="h-4 w-4 text-gray-500"
											/>
											<span class="text-sm">
												{{
													editingInput
														? fieldTypeOptions.find((opt) => opt.value === editingInput!.type)?.label
														: ""
												}}
											</span>
										</div>
									</template>
								</Autocomplete>
							</div>
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Description</label>
								<TextInput v-model="editingInput.description" placeholder="Enter description (optional)" />
							</div>
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Default Value</label>
								<TextInput v-model="editingInput.defaultValue" placeholder="Enter default value (optional)" />
							</div>
							<div class="flex gap-2">
								<Button variant="solid" @click="saveInput">Save</Button>
								<Button variant="outline" @click="cancelEdit">Cancel</Button>
							</div>
						</div>
					</template>
				</Popover>
			</div>

			<EmptyState v-else message="No inputs added" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Autocomplete, TextInput, Popover } from "frappe-ui"
import Block from "@/utils/block"
import EmptyState from "@/components/EmptyState.vue"
import type { SelectOption } from "@/types"

const props = defineProps<{
	block?: Block
}>()

interface ComponentInput {
	name: string
	type: string
	description?: string
	defaultValue?: string
	showPopover?: boolean
}

const componentInputs = ref<ComponentInput[]>([])
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
	{ label: "URL", value: "url" },
]

const getFieldTypeIcon = (type: string) => {
	const iconMap: Record<string, string> = {
		text: "type",
		number: "hash",
		checkbox: "check-square",
		textarea: "align-left",
		select: "list",
		code: "code",
		color: "palette",
		url: "link",
	}
	return iconMap[type] || "help-circle"
}

const editInput = (input: ComponentInput, index: number) => {
	editingInput.value = { ...input }
	editingIndex.value = index
	showEditPopover.value = true
}

const saveInput = () => {
	if (editingInput.value && editingIndex.value >= 0) {
		componentInputs.value[editingIndex.value] = { ...editingInput.value }
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
	// Create new input immediately with type as name
	const fieldTypeLabel = fieldTypeOptions.find((opt) => opt.value === fieldType)?.label || fieldType
	const newInputData: ComponentInput = {
		name: fieldTypeLabel,
		type: fieldType,
		description: "",
		defaultValue: "",
	}

	// Add to componentInputs
	componentInputs.value.push(newInputData)

	// Set up for editing the newly added input
	const newIndex = componentInputs.value.length - 1
	setTimeout(() => {
		editInput(newInputData, newIndex)
	}, 10) // Small delay to ensure DOM is updated
}

const removeInput = (index: number) => {
	componentInputs.value.splice(index, 1)
}
</script>
