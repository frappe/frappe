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
					v-model:show="input.showPopover"
					placement="bottom-start"
				>
					<template #target>
						<div
							class="group flex cursor-pointer items-center justify-between rounded-lg border border-transparent px-3 py-2 hover:border-gray-200 hover:bg-gray-50"
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
					<template #body>
						<div class="w-64 space-y-4 p-4">
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Name</label>
								<TextInput v-model="input.name" placeholder="Enter input name" />
							</div>
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Type</label>
								<Autocomplete
									:options="fieldTypeOptions"
									:modelValue="fieldTypeOptions.find((opt) => opt.value === input.type)"
									@update:modelValue="(option: SelectOption) => (input.type = option.value)"
								>
									<template #target="{ togglePopover }">
										<div
											@click="togglePopover"
											class="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 hover:bg-gray-50"
										>
											<FeatherIcon :name="getFieldTypeIcon(input.type)" class="h-4 w-4 text-gray-500" />
											<span class="text-sm">
												{{ fieldTypeOptions.find((opt) => opt.value === input.type)?.label }}
											</span>
										</div>
									</template>
								</Autocomplete>
							</div>
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Description</label>
								<TextInput v-model="input.description" placeholder="Enter description (optional)" />
							</div>
							<div>
								<label class="mb-1 block text-sm font-medium text-gray-700">Default Value</label>
								<TextInput v-model="input.defaultValue" placeholder="Enter default value (optional)" />
							</div>
							<div class="flex gap-2">
								<Button variant="solid" @click="saveInput(index)">Save</Button>
								<Button variant="outline" @click="input.showPopover = false">Cancel</Button>
							</div>
						</div>
					</template>
				</Popover>
			</div>

			<EmptyState v-else message="No inputs added" />
		</div>

		<!-- Add Input Popover -->
		<Popover v-model:show="showAddInput" placement="bottom-start">
			<template #target>
				<div ref="addInputTarget"></div>
			</template>
			<template #body>
				<div class="space-y-4 p-4">
					<div>
						<label class="mb-1 block text-sm font-medium text-gray-700">Name</label>
						<TextInput v-model="newInput.name" placeholder="Enter input name" />
					</div>
					<div>
						<label class="mb-1 block text-sm font-medium text-gray-700">Description</label>
						<TextInput v-model="newInput.description" placeholder="Enter description (optional)" />
					</div>
					<div>
						<label class="mb-1 block text-sm font-medium text-gray-700">Default Value</label>
						<TextInput v-model="newInput.defaultValue" placeholder="Enter default value (optional)" />
					</div>
					<div class="flex gap-2">
						<Button variant="solid" @click="addInput" :disabled="!newInput.name">Add Input</Button>
						<Button variant="outline" @click="cancelAddInput">Cancel</Button>
					</div>
				</div>
			</template>
		</Popover>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Autocomplete, TextInput, Popover, Badge } from "frappe-ui"
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
const showAddInput = ref(false)
const addInputTarget = ref<HTMLElement>()
const newInput = ref<ComponentInput>({
	name: "",
	type: "",
	description: "",
	defaultValue: "",
})

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
		textarea: "align-left",
		checkbox: "toggle-left",
		select: "list",
		code: "code",
		color: "palette",
		email: "mail",
		url: "link",
	}
	return iconMap[type] || "help-circle"
}

const editInput = (input: ComponentInput, index: number) => {
	input.showPopover = true
}

const saveInput = (index: number) => {
	componentInputs.value[index].showPopover = false
}

const showAddInputPopover = (fieldType: string) => {
	newInput.value = {
		name: "",
		type: fieldType,
		description: "",
		defaultValue: "",
	}
	showAddInput.value = true
}

const addInput = () => {
	if (!newInput.value.name) return

	componentInputs.value.push({ ...newInput.value })

	// Reset form
	newInput.value = {
		name: "",
		type: "",
		description: "",
		defaultValue: "",
	}
	showAddInput.value = false
}

const cancelAddInput = () => {
	newInput.value = {
		name: "",
		type: "",
		description: "",
		defaultValue: "",
	}
	showAddInput.value = false
}

const removeInput = (index: number) => {
	componentInputs.value.splice(index, 1)
}
</script>
