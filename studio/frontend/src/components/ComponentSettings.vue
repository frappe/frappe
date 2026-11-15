<template>
	<div class="flex select-none flex-col gap-5 pb-16">
		<div class="flex items-start justify-between gap-2">
			<div class="flex min-w-0 items-center gap-2.5">
				<span :class="isGlobal ? 'lucide-globe' : 'lucide-box'" class="h-4 w-4 shrink-0 text-ink-purple-5" />
				<div class="min-w-0">
					<p class="truncate text-base-medium text-ink-gray-9">{{ componentDoc?.component_name }}</p>
					<p class="truncate font-mono text-xs text-ink-gray-5">{{ componentId }}</p>
				</div>
			</div>
			<Dropdown :options="componentMenu">
				<Button variant="ghost" icon="lucide-ellipsis" title="Component actions" />
			</Dropdown>
		</div>

		<ErrorMessage v-if="scriptError" :message="scriptError" />

		<div class="flex flex-col gap-2">
			<SectionContainer title="Props">
				<template #actions>
					<Combobox
						v-if="!propsReadOnlyReason"
						:options="fieldTypeOptions"
						@update:modelValue="(value: string) => showAddInputPopover(value)"
						class="!w-auto"
					>
						<template #trigger>
							<Button size="sm" variant="ghost" icon="lucide-plus" title="Add prop" />
						</template>
					</Combobox>
				</template>

				<p v-if="propsReadOnlyReason" class="text-sm text-ink-gray-5">
					{{ propsReadOnlyReason }}
					<button class="underline" @click="store.navigateToComponentScript(componentId)">Open script</button>
				</p>

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
						side="left"
						align="start"
						:offset="16"
					>
						<template #trigger>
							<div
								class="group flex h-8 w-full shrink-0 items-center justify-between gap-2 rounded-4 border border-outline-gray-2 px-2"
								:class="propsReadOnlyReason ? '' : 'cursor-pointer hover:bg-surface-gray-1'"
								@click="!propsReadOnlyReason && editInput(input, index)"
							>
								<div class="flex min-w-0 items-center gap-2">
									<span :class="getFieldTypeIcon(input.type)" class="h-4 w-4 shrink-0 text-ink-gray-4" />
									<span class="truncate text-sm text-ink-gray-7">{{ input.input_name }}</span>
									<span v-if="input.required" class="text-sm text-ink-red-4" title="Required">*</span>
								</div>
								<span
									class="truncate text-xs text-ink-gray-5"
									:class="propsReadOnlyReason ? '' : 'group-hover:hidden'"
								>
									{{ input.default }}
								</span>
								<button
									v-if="!propsReadOnlyReason"
									class="hidden cursor-pointer items-center rounded-1 p-1 text-ink-gray-6 hover:text-ink-gray-8 group-hover:flex"
									title="Remove prop"
									@click.stop="removeInput(input)"
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
									:options="editingInput.type === 'select' ? defaultOptions : undefined"
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

				<EmptyState v-else-if="!propsReadOnlyReason" message="No props. Add one to let a page pass a value." />

				<template v-if="componentInputs.length">
					<button
						class="flex items-center gap-1 self-start text-sm text-ink-gray-6 hover:text-ink-gray-8"
						@click="showPreviewValues = !showPreviewValues"
					>
						<span
							:class="showPreviewValues ? 'lucide-chevron-down' : 'lucide-chevron-right'"
							class="h-3.5 w-3.5"
						/>
						Preview values
					</button>
					<template v-if="showPreviewValues">
						<p class="text-sm text-ink-gray-5">Values for this preview only. They are not saved.</p>
						<PropsEditor
							v-if="componentEditorStore.studioComponentBlock"
							:block="componentEditorStore.studioComponentBlock"
							:isTestingComponent="true"
						/>
					</template>
				</template>
			</SectionContainer>

			<SectionContainer v-if="emits.length" title="Events">
				<div class="flex flex-col gap-1">
					<div
						v-for="event in emits"
						:key="event"
						class="flex h-8 items-center gap-2 rounded-4 border border-outline-gray-2 px-2"
					>
						<span class="lucide-zap h-4 w-4 text-ink-gray-4" />
						<span class="text-sm text-ink-gray-7">{{ event }}</span>
					</div>
				</div>
			</SectionContainer>

		</div>

		<div class="flex flex-col gap-1">
			<div class="flex items-center justify-between">
				<h3 class="text-base-medium text-ink-gray-9">Global component</h3>
				<Switch
					aria-label="Global component"
					:modelValue="isGlobal"
					:disabled="changingScope"
					@update:modelValue="setGlobal"
				/>
			</div>
			<p class="text-sm text-ink-gray-5">All apps can use it.</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, markRaw, computed } from "vue"
import { Combobox, Dropdown, ErrorMessage, Popover, FormControl, Button, Switch, dialog } from "frappe-ui"
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
import { confirm, isCtrlOrCmd } from "@/utils/helpers"
import { getPropsReadOnlyReason } from "@/utils/componentScriptProps"

const store = useStudioStore()
const componentStore = useComponentStore()
const componentEditorStore = useComponentEditorStore()
const componentInputs = computed(() => componentEditorStore.componentInputs)

const canvasStore = useCanvasStore()
const componentId = computed(() => canvasStore.fragmentData.fragmentId ?? "")
const componentDoc = computed(() => componentStore.getComponentDoc(componentId.value))
const isGlobal = computed(() => !componentDoc.value?.studio_app)
const scriptError = computed(() => componentStore.componentScriptErrors.get(componentId.value))
const emits = computed(() => componentStore.getComponentEmits(componentId.value))

const componentMenu = [
	{ label: "Rename", icon: "lucide-pencil", onClick: renameComponent },
	{ label: "Delete", icon: "lucide-trash", theme: "red", onClick: deleteComponent },
]

function renameComponent() {
	dialog.prompt({
		title: "Rename Component",
		confirmLabel: "Rename",
		fields: [
			{
				name: "componentName",
				label: "Component Name",
				required: true,
				defaultValue: componentDoc.value.component_name,
			},
		],
		onConfirm: ({ values }: { values: Record<string, any> }) =>
			componentEditorStore.renameComponent(componentId.value, values.componentName),
	})
}

async function deleteComponent() {
	if (await componentEditorStore.deleteComponent(componentDoc.value)) canvasStore.resetFragments()
}

const showPreviewValues = ref(false)

const changingScope = ref(false)
async function setGlobal(value: boolean) {
	changingScope.value = true
	await componentEditorStore.setGlobal(componentId.value, value)
	changingScope.value = false
}

// The form writes each prop into the script. A script that builds its props in another way
// is changed by hand.
const propsReadOnlyReason = computed(() => {
	// an older component: its input rows still work, and a script with props replaces them
	if (!componentDoc.value?.script?.trim() && componentDoc.value?.inputs?.length) {
		return "This component declares its inputs in an older format. Declare them as props in a script to change them."
	}
	return getPropsReadOnlyReason(componentDoc.value?.script || "")
})
// a new prop is in the list while its form is open, and in the script after it is saved
const draftInput = ref<ComponentInput | null>(null)
const shownInputs = computed(() =>
	draftInput.value ? [...componentInputs.value, draftInput.value] : componentInputs.value,
)
const defaultOptions = computed(() => {
	const options = (editingInput.value?.options || "").split("\n").filter((option) => option.trim())
	return [{ label: "No default", value: "" }, ...options.map((option) => ({ label: option, value: option }))]
})
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

async function removeInput(input: ComponentInput) {
	if (await confirm(`Remove the prop '${input.input_name}' from the component's script?`)) {
		componentEditorStore.saveComponentProp(componentId.value, input, null)
	}
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

const DEFAULT_CONTROLS: Record<string, string> = {
	number: "number",
	checkbox: "checkbox",
	textarea: "textarea",
	select: "select",
}

const setInputControl = () => {
	const input = editingInput.value
	if (!input) return
	// a checkbox holds true or false, and each other control holds text
	if (input.type === "checkbox") input.default = ["true", "1"].includes(String(input.default))
	else if (typeof input.default === "boolean") input.default = ""

	if (input.type === "code") {
		input.inputControl = markRaw(Code)
	} else if (input.type === "color") {
		input.inputControl = markRaw(ColorInput)
	} else {
		input.inputControl = "FormControl"
		input.inputType = DEFAULT_CONTROLS[input.type] ?? "text"
	}
}

const handleInputKeydown = (e: KeyboardEvent) => {
	if (isCtrlOrCmd(e) && e.key === "s") {
		e.preventDefault()
		saveInput()
	}
}
</script>
