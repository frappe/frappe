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
						:options="PROP_TYPES"
						@update:modelValue="(value: string) => showAddPropPopover(value)"
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

				<div class="flex flex-col gap-1" v-if="shownProps.length > 0">
					<Popover
						v-for="(prop, index) in shownProps"
						:key="prop.input_name"
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
								@click="!propsReadOnlyReason && editProp(prop, index)"
							>
								<div class="flex min-w-0 items-center gap-2">
									<span :class="getFieldTypeIcon(prop.type)" class="h-4 w-4 shrink-0 text-ink-gray-4" />
									<span class="truncate text-sm text-ink-gray-7">{{ prop.input_name }}</span>
									<span v-if="prop.required" class="text-sm text-ink-red-4" title="Required">*</span>
								</div>
								<span
									class="truncate text-xs text-ink-gray-5"
									:class="propsReadOnlyReason ? '' : 'group-hover:hidden'"
								>
									{{ prop.default }}
								</span>
								<button
									v-if="!propsReadOnlyReason"
									class="hidden cursor-pointer items-center rounded-1 p-1 text-ink-gray-6 hover:text-ink-gray-8 group-hover:flex"
									title="Remove prop"
									@click.stop="removeProp(prop)"
								>
									<span class="lucide-x h-4 w-4" />
								</button>
							</div>
						</template>
						<template #default>
							<div
								class="w-64 space-y-4 p-4"
								v-if="editingProp && editingIndex === index"
								@keydown="handlePropKeydown"
							>
								<FormControl
									type="text"
									label="Name"
									v-model="editingProp.input_name"
									placeholder="e.g. title"
									autocomplete="off"
									:required="true"
								/>
								<FormControl
									type="combobox"
									label="Type"
									:options="typeOptions"
									:modelValue="editingProp.prop_type"
									@update:modelValue="(value: string) => setType(value)"
									:required="true"
								/>
								<FormControl
									v-if="controlOptions.length > 1"
									type="combobox"
									label="Control"
									:options="controlOptions"
									:modelValue="editingProp.control || null"
									@update:modelValue="(value: string) => setControl(value)"
								/>
								<FormControl
									v-if="editingProp.type === 'select'"
									type="textarea"
									label="Options"
									v-model="editingProp.options"
									:required="true"
									placeholder="Enter list of options, each on a new line"
								/>

								<!-- Default value -->
								<component
									:is="defaultControl.is"
									:type="defaultControl.type"
									:options="editingProp.type === 'select' ? defaultOptions : undefined"
									label="Default Value"
									v-model="editingProp.default"
								/>
								<FormControl
									type="textarea"
									label="Description"
									v-model="editingProp.description"
									placeholder="Enter description (optional)"
								/>
								<FormControl
									type="checkbox"
									label="Is Required"
									size="sm"
									v-model="editingProp.required"
									class="[&>label]:text-sm [&>label]:text-ink-gray-5"
								/>
								<div class="flex gap-2">
									<Button variant="solid" @click="saveProp">Save</Button>
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

				<template v-if="declaredProps.length">
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
import { ref, computed } from "vue"
import { Combobox, Dropdown, ErrorMessage, Popover, FormControl, Button, Switch, dialog, toast } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import type { StudioComponentInput } from "@/runtime/types/Studio/StudioComponent"
import Code from "@/components/Code.vue"
import ColorInput from "@/components/ColorInput.vue"
import PropsEditor from "@/components/PropsEditor.vue"
import SectionContainer from "@/components/SectionContainer.vue"
import useComponentEditorStore from "@/stores/componentEditorStore"
import useComponentStore from "@/runtime/stores/componentStore"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { confirm, isCtrlOrCmd } from "@/utils/helpers"
import { getPropReadOnlyReason, getPropsReadOnlyReason } from "@/utils/componentScriptProps"
import { getTypeControls } from "@/runtime/utils/componentScript"

const store = useStudioStore()
const componentStore = useComponentStore()
const componentEditorStore = useComponentEditorStore()
const declaredProps = computed(() => componentEditorStore.declaredProps)

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
	// an older component: its prop rows still work, and a script with props replaces them
	if (!componentDoc.value?.script?.trim() && componentDoc.value?.inputs?.length) {
		return "This component declares its inputs in an older format. Declare them as props in a script to change them."
	}
	return getPropsReadOnlyReason(componentDoc.value?.script || "")
})
// a new prop is in the list while its form is open, and in the script after it is saved
const draftProp = ref<StudioComponentInput | null>(null)
const shownProps = computed(() =>
	draftProp.value ? [...declaredProps.value, draftProp.value] : declaredProps.value,
)
const defaultOptions = computed(() => {
	const options = (editingProp.value?.options || "").split("\n").filter((option) => option.trim())
	return [{ label: "No default", value: "" }, ...options.map((option) => ({ label: option, value: option }))]
})
const showEditPopover = ref(false)
const editingProp = ref<StudioComponentInput | null>(null)
const editingIndex = ref<number>(-1)

const PROP_TYPES = ["String", "Number", "Boolean", "Array", "Object", "Any"]
// also a type that the form cannot write, such as "String | Number", while the prop has it
const typeOptions = computed(() => [...new Set([...PROP_TYPES, editingProp.value?.prop_type || "Any"])])

const CONTROL_LABELS: Record<string, string> = {
	text: "Text",
	textarea: "Textarea",
	select: "Select",
	color: "Color",
	number: "Number",
	checkbox: "Checkbox",
	code: "Code",
}
const controlOptions = computed(() =>
	getTypeControls(editingProp.value?.prop_type).map((value) => ({ label: CONTROL_LABELS[value], value })),
)

function setType(propType: string) {
	if (!editingProp.value) return
	Object.assign(editingProp.value, { prop_type: propType, control: "", default: "" })
	setDefaultControl()
}

function setControl(control: string) {
	if (!editingProp.value) return
	editingProp.value.control = control
	setDefaultControl()
}

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

const editProp = (prop: StudioComponentInput, index: number) => {
	const readOnlyReason = getPropReadOnlyReason(componentDoc.value?.script || "", prop.input_name)
	if (readOnlyReason) return toast.warning(readOnlyReason)
	editingProp.value = { ...prop }
	editingIndex.value = index
	setDefaultControl()
	showEditPopover.value = true
}

const saveProp = async () => {
	if (!editingProp.value) return
	const previous = declaredProps.value[editingIndex.value] ?? null
	if (await componentEditorStore.saveComponentProp(componentId.value, previous, editingProp.value)) cancelEdit()
}

async function removeProp(prop: StudioComponentInput) {
	if (await confirm(`Remove the prop '${prop.input_name}' from the component's script?`)) {
		componentEditorStore.saveComponentProp(componentId.value, prop, null)
	}
}

const cancelEdit = () => {
	showEditPopover.value = false
	editingProp.value = null
	editingIndex.value = -1
	draftProp.value = null
}

const showAddPropPopover = (propType: string) => {
	const names = declaredProps.value.map((prop) => prop.input_name)
	let name = "prop"
	for (let count = 2; names.includes(name); count++) name = `prop${count}`
	const type = getTypeControls(propType)[0]
	draftProp.value = { input_name: name, type, prop_type: propType, control: "", description: "", default: "" }
	setTimeout(() => {
		editProp(draftProp.value!, declaredProps.value.length)
	}, 10) // Small delay to ensure DOM is updated
}

const FORM_CONTROL_TYPES: Record<string, string> = {
	number: "number",
	checkbox: "checkbox",
	textarea: "textarea",
	select: "select",
}

// the control that edits the default value in the form
const defaultControl = computed(() => {
	const control = editingProp.value?.type ?? "text"
	if (control === "code") return { is: Code }
	if (control === "color") return { is: ColorInput }
	return { is: "FormControl", type: FORM_CONTROL_TYPES[control] ?? "text" }
})

const setDefaultControl = () => {
	const prop = editingProp.value
	if (!prop) return
	prop.type = prop.control || getTypeControls(prop.prop_type)[0]
	// a checkbox holds true or false, and each other control holds text
	if (prop.type === "checkbox") prop.default = ["true", "1"].includes(String(prop.default))
	else if (typeof prop.default === "boolean") prop.default = ""
}

const handlePropKeydown = (e: KeyboardEvent) => {
	if (isCtrlOrCmd(e) && e.key === "s") {
		e.preventDefault()
		saveProp()
	}
}
</script>
