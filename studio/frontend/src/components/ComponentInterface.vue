<template>
	<div class="flex select-none flex-col pb-16">
		<div class="flex flex-col gap-3">
			<FormControl
				type="checkbox"
				label="Global Component"
				v-model="componentEditorStore.isGlobal"
				:title="'All apps can use a global component. Uncheck it to keep the component in this app.'"
			/>
			<SectionContainer title="Script">
				<template #actions>
					<Button
						size="sm"
						variant="ghost"
						:icon="isScripted ? 'lucide-pencil' : 'lucide-plus'"
						:title="isScripted ? 'Edit script' : 'Add script'"
						@click="store.navigateToComponentScript(componentId)"
					/>
				</template>
				<ErrorMessage v-if="scriptError" :message="scriptError" />
				<p v-else class="text-sm text-ink-gray-5">
					{{
						isScripted
							? "The script declares this component's props and events."
							: "Add a script to give this component state, logic and events."
					}}
				</p>
			</SectionContainer>

			<SectionContainer title="Props">
				<template #actions>
					<Combobox
						v-if="!propsReadOnlyReason"
						:options="fieldTypeOptions"
						@update:modelValue="(value: string) => showAddInputPopover(value)"
						class="!w-auto"
					>
						<template #trigger>
							<Button size="sm" variant="ghost" icon="lucide-plus" />
						</template>
					</Combobox>
				</template>

				<div class="flex flex-col gap-1" v-if="shownInputs.length > 0">
					<Popover
						v-for="(input, index) in shownInputs"
						:key="input.input_name"
						:open="showEditPopover && editingIndex === index"
						@update:open="
							(open: boolean) => {
								if (!open) cancelEdit()
							}
						"
						trigger="manual"
						side="bottom"
						align="center"
					>
						<template #trigger>
							<div
								class="group flex flex-1 justify-between rounded-4 border border-outline-gray-2 px-2 py-1"
								:class="propsReadOnlyReason ? '' : 'cursor-pointer hover:bg-surface-gray-1'"
								@click="!propsReadOnlyReason && editInput(input, index)"
							>
								<div class="flex items-center gap-2">
									<span :class="getFieldTypeIcon(input.type)" class="h-4 w-4 text-ink-gray-4" />
									<span class="text-sm text-ink-gray-7">{{ input.input_name }}</span>
								</div>
								<button
									v-if="!propsReadOnlyReason"
									class="flex cursor-pointer items-center rounded-1 p-1 text-ink-gray-6 opacity-0 transition-opacity hover:text-ink-gray-8 group-hover:opacity-100"
									@click.stop="componentEditorStore.saveComponentProp(componentId, input, null)"
								>
									<span class="lucide-x h-4 w-4" />
								</button>
							</div>
						</template>
						<template #default>
							<div
								class="w-64 space-y-4 p-4"
								v-if="editingInput && editingIndex === index"
								@keydown="handleInputKeydown"
							>
								<FormControl
									type="text"
									label="Name"
									v-model="editingInput.input_name"
									placeholder="e.g. title"
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
										<span
											:class="editingInput ? getFieldTypeIcon(editingInput.type) : 'lucide-circle-help'"
											class="mr-1 h-3 w-3 text-ink-gray-4"
										/>
									</template>
									<template #item-prefix="{ item }">
										<span :class="getFieldTypeIcon(item.value)" class="h-3 w-3 text-ink-gray-4" />
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
									<kbd class="rounded-4 bg-surface-gray-2 px-1 py-0.5">⌘</kbd>
									+
									<kbd class="rounded-4 bg-surface-gray-2 px-1 py-0.5">S</kbd>
									to save
								</div>
							</div>
						</template>
					</Popover>
				</div>

				<EmptyState v-else message="No props added" />
				<p v-if="propsReadOnlyReason" class="text-sm text-ink-gray-5">{{ propsReadOnlyReason }}</p>
			</SectionContainer>

			<SectionContainer title="Test Props">
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
import { ref, markRaw, computed, watch } from "vue"
import { Combobox, ErrorMessage, Popover, FormControl, Button } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import type { ComponentInput } from "@/types/Studio/StudioComponent"
import Code from "@/components/Code.vue"
import ColorInput from "@/components/ColorInput.vue"
import PropsEditor from "@/components/PropsEditor.vue"
import SectionContainer from "@/components/SectionContainer.vue"
import useComponentEditorStore from "@/stores/componentEditorStore"
import useComponentStore from "@/stores/componentStore"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { isCtrlOrCmd } from "@/utils/helpers"
import { getPropsReadOnlyReason } from "@/utils/componentScriptProps"

const store = useStudioStore()
const componentStore = useComponentStore()
const componentEditorStore = useComponentEditorStore()
const componentInputs = computed(() => componentEditorStore.componentInputs)

const canvasStore = useCanvasStore()
const componentId = computed(() => canvasStore.fragmentData.fragmentId ?? "")
const script = computed(() => componentStore.getComponentScript(componentId.value))
const isScripted = computed(() => componentStore.hasComponentScript(componentId.value))
const scriptError = computed(() => componentStore.componentScriptErrors.get(componentId.value))
// A scripted component declares its inputs as props, so they follow the script.
watch(script, () => componentId.value && componentEditorStore.setComponentInputs(componentId.value))
// The form writes each prop into the script. A script that builds its props in another way
// is changed by hand.
const propsReadOnlyReason = computed(() => {
	const componentDoc = componentStore.getComponentDoc(componentId.value)
	// an older component: its input rows still work, and a script with props replaces them
	if (!componentDoc?.script?.trim() && componentDoc?.inputs?.length) {
		return "This component declares its inputs in an older format. Declare them as props in a script to change them."
	}
	return getPropsReadOnlyReason(componentDoc?.script || "")
})
// a new prop is in the list while its form is open, and in the script after it is saved
const draftInput = ref<ComponentInput | null>(null)
const shownInputs = computed(() =>
	draftInput.value ? [...componentInputs.value, draftInput.value] : componentInputs.value,
)
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
		text: "lucide-type",
		number: "lucide-hash",
		checkbox: "lucide-square-check",
		textarea: "lucide-text-align-start",
		select: "lucide-list",
		code: "lucide-code",
		color: "lucide-droplet",
	}
	return iconMap[type] || "lucide-type"
}

const editInput = (input: ComponentInput, index: number) => {
	editingInput.value = { ...input }
	editingIndex.value = index
	setInputControl()
	showEditPopover.value = true
}

const saveInput = async () => {
	if (!editingInput.value) return
	const { inputControl, inputType, showPopover, ...input } = editingInput.value
	const previous = componentInputs.value[editingIndex.value] ?? null
	if (await componentEditorStore.saveComponentProp(componentId.value, previous, input)) cancelEdit()
}

const cancelEdit = () => {
	showEditPopover.value = false
	editingInput.value = null
	editingIndex.value = -1
	draftInput.value = null
}

const showAddInputPopover = (fieldType: string) => {
	const names = componentInputs.value.map((input) => input.input_name)
	let name = fieldType
	for (let count = 2; names.includes(name); count++) name = `${fieldType}${count}`
	draftInput.value = { input_name: name, type: fieldType, description: "", default: "" }
	setTimeout(() => {
		editInput(draftInput.value!, componentInputs.value.length)
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
