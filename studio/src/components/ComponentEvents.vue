<template>
	<div class="flex flex-col">
		<div v-if="block" class="flex flex-col gap-3">
			<div class="flex w-full flex-col space-y-1" v-if="!isObjectEmpty(block?.componentEvents)">
				<div
					v-for="(event, name) in block?.componentEvents"
					:key="name"
					class="group/item flex w-full cursor-pointer flex-row items-center justify-between gap-2 rounded border-[1px] border-outline-gray-2 px-2 py-2"
				>
					<div class="gap-1 self-center truncate text-base text-ink-gray-6">{{ name }}</div>
					<ItemActions :menuOptions="getEventMenu(event)" @edit="openEvent(event)" />
				</div>
			</div>

			<EmptyState v-else message="No events added" />

			<Button class="mt-2" icon-left="plus" @click="showAddEventDialog = true">Add Event</Button>
			<Dialog
				v-model="showAddEventDialog"
				:title="(newEvent.isEditing ? 'Edit Event' : 'Add Event') + ' - ' + block.getBlockDescription()"
				size="3xl"
				:actions="[
					{
						label: newEvent.isEditing ? 'Update' : 'Add',
						variant: 'solid',
						onClick: () => saveEvent(newEvent),
					},
				]"
				:dismissible="false"
				@after-leave="newEvent = { ...emptyEvent, fields: [], isEditing: false }"
			>
				<template #default>
					<div class="flex flex-col gap-3">
						<Combobox
							:options="eventOptions"
							:allowCustomValue="true"
							label="Event"
							v-model="newEvent.event"
							description="Type any event, optionally with modifiers — e.g. keydown.enter, click.prevent, submit.prevent.stop"
						/>
						<Combobox :options="Object.keys(actions)" label="Action" v-model="newEvent.action" />
						<component
							v-for="control in actionControls"
							:key="control.component.name"
							:is="control.component"
							v-bind="control.getProps()"
							v-on="control.events || {}"
							:class="control.class || ''"
						/>

						<template v-if="showSuccessFailureOptions">
							<!-- Success Section -->
							<div class="border-t border-outline-elevation-2 pt-4">
								<div class="mb-3">
									<h3 class="text-sm-medium mb-2 text-ink-gray-8">On Success</h3>
									<TabButtons
										:buttons="[
											{ label: 'Message', value: 'message' },
											{ label: 'Script', value: 'script' },
										]"
										v-model="newEvent.on_success"
										class="!w-fit"
									/>
								</div>
								<FormControl
									v-if="newEvent.on_success === 'message'"
									type="textarea"
									label="Success Message"
									v-model="newEvent.success_message"
									autocomplete="off"
									:description="
										newEvent.action === 'Insert a Document'
											? `Default: ${newEvent.doctype} created successfully`
											: ''
									"
								/>
								<Code
									v-else
									label="Script"
									:completions="
										(context: CompletionContext) =>
											getEditorCompletions(context, props.block?.getCompletions())
									"
									:emitOnChange="true"
									:modelValue="newEvent.on_success_script?.toString()"
									@update:modelValue="(val: string) => (newEvent.on_success_script = val)"
									@save="saveEvent(newEvent)"
								/>
							</div>

							<!-- Failure Section -->
							<div class="border-t border-outline-elevation-2 pt-4">
								<div class="mb-3">
									<h3 class="text-sm-medium mb-2 text-ink-gray-8">On Failure</h3>
									<TabButtons
										:buttons="[
											{ label: 'Message', value: 'message' },
											{ label: 'Script', value: 'script' },
										]"
										v-model="newEvent.on_error"
										class="!w-fit"
									/>
								</div>
								<FormControl
									v-if="newEvent.on_error === 'message'"
									type="textarea"
									label="Error Message"
									v-model="newEvent.error_message"
									autocomplete="off"
									:description="
										newEvent.action === 'Insert a Document'
											? `Default: Failed to create ${newEvent.doctype}`
											: ''
									"
								/>
								<Code
									v-else
									label="Script"
									:completions="
										(context: CompletionContext) =>
											getEditorCompletions(context, props.block?.getCompletions())
									"
									:emitOnChange="true"
									:modelValue="newEvent.on_error_script?.toString()"
									@update:modelValue="(val: string) => (newEvent.on_error_script = val)"
								/>
							</div>

							<span
								class="mt-1 text-p-xs text-ink-gray-6"
								v-html="getScriptDescription(newEvent.event)"
							></span>
						</template>
					</div>
				</template>
			</Dialog>
		</div>

		<EmptyState v-else message="Select a block to edit events" />
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { Combobox, FormControl, createResource, Dialog, TabButtons } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import Block from "@/utils/block"
import EmptyState from "@/components/EmptyState.vue"
import ItemActions from "@/components/ItemActions.vue"

import { isObjectEmpty, confirm } from "@/utils/helpers"

import type { ActionConfigurations, ComponentEvent } from "@/types/ComponentEvent"
import { Link } from "frappe-ui/frappe"
import Grid from "@/components/Grid.vue"
import Code from "@/components/Code.vue"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { DocTypeField } from "@/types"
import { toast } from "frappe-ui"
import type { CompletionContext } from "@codemirror/autocomplete"
import useCodeStore from "@/stores/codeStore"
import useComponentInstance from "@/utils/useComponentInstance"

const props = defineProps<{
	block?: Block
}>()
const store = useStudioStore()
const getEditorCompletions = useStudioCompletions(true)

const showAddEventDialog = ref(false)
const emptyEvent: ComponentEvent = {
	event: "click",
	action: "Run Script",
	// insert document
	doctype: "",
	fields: [],
	on_success: "message",
	success_message: "",
	on_success_script: "",
	on_error: "message",
	error_message: "",
	on_error_script: "",
	// run script
	script: "",
}
const newEvent = ref<ComponentEvent>({ ...emptyEvent })

const eventOptions = computed(() => {
	if (!props.block || props.block.isRoot()) return []
	return [
		"click",
		"change",
		"focus",
		"blur",
		"submit",
		"keydown",
		"keyup",
		"keypress",
		...componentEvents.value,
	]
})

const componentInstance = useComponentInstance(() => props.block)

const componentEvents = computed(() => {
	if (!componentInstance.value || typeof componentInstance.value === "string") {
		return []
	}
	return componentInstance.value?.emits || []
})

const doctypeFields = ref<{ label: string; value: string }[]>([])
watch(
	() => newEvent.value.doctype,
	async (value, oldValue) => {
		if (value === oldValue || !value) return

		const fields = createResource({
			url: "studio.api.get_doctype_fields",
			params: { doctype: value },
			transform: (data: DocTypeField[]) => {
				return data.map((field) => {
					return {
						label: field.fieldname,
						value: field.fieldname,
					}
				})
			},
		})
		await fields.reload()
		doctypeFields.value = fields.data

		if (!newEvent.value.isEditing) {
			newEvent.value.fields = []
			const codeStore = useCodeStore()
			doctypeFields.value.forEach((field) => {
				newEvent.value.fields?.push({
					field: field.value,
					value: Object.keys(codeStore.variables).includes(field.value) ? field.value : "",
					name: field.value,
				})
			})
		}
	},
)

const actions: ActionConfigurations = {
	"Run Script": [
		{
			component: Code,
			getProps: () => {
				return {
					label: "Script",
					isFormInput: true,
					language: "javascript",
					modelValue: newEvent.value.script,
					height: "400px",
					maxHeight: "400px",
					emitOnChange: true,
					description: getScriptDescription(newEvent.value.event),
					completions: (context: CompletionContext) =>
						getEditorCompletions(context, props.block?.getCompletions()),
				}
			},
			events: {
				"update:modelValue": (val: any) => {
					newEvent.value.script = val
				},
				save: () => saveEvent(newEvent.value),
			},
		},
	],
	"Insert a Document": [
		{
			component: Link,
			getProps: () => {
				return {
					label: "Document Type",
					required: true,
					doctype: "DocType",
					modelValue: newEvent.value.doctype,
				}
			},
			events: {
				"update:modelValue": (val: string) => {
					newEvent.value.doctype = val
				},
			},
		},
		{
			component: Grid,
			getProps: () => {
				return {
					label: "Fields",
					columns: [
						{ label: "Field", fieldname: "field", fieldtype: "select", options: doctypeFields.value },
						{
							label: "Variable",
							fieldname: "value",
							fieldtype: "select",
							options: [...store.variableOptions, ...store.pageScriptBindingOptions],
						},
					],
					rows: newEvent.value.fields,
					showDeleteBtn: true,
				}
			},
			events: {
				"update:rows": (val: any) => {
					newEvent.value.fields = val
				},
			},
		},
	],
}

const actionControls = computed(() => {
	return actions[newEvent.value.action] || []
})

const showSuccessFailureOptions = computed(() => {
	return newEvent.value.action === "Insert a Document" && newEvent.value.doctype
})

function getFnBoilerplate(event: "success" | "error") {
	if (event === "success") {
		return "function onSuccess(data) {}"
	} else {
		return "function onError(error) {}"
	}
}

watch(
	() => [newEvent.value.on_success, newEvent.value.on_error],
	() => {
		if (newEvent.value.on_success === "script" && !newEvent.value.on_success_script) {
			newEvent.value.on_success_script = getFnBoilerplate("success")
		}
		if (newEvent.value.on_error === "script" && !newEvent.value.on_error_script) {
			newEvent.value.on_error_script = getFnBoilerplate("error")
		}
	},
)

function getEvent(event: ComponentEvent): ComponentEvent {
	let _event: ComponentEvent = {
		event: event.event,
		action: event.action,
	}
	if (event.action === "Run Script") {
		_event.script = event.script || ""
	} else if (event.action === "Insert a Document") {
		_event.doctype = event.doctype
		_event.fields = event.fields
		setEventCallbackFields(_event, event)
	}

	if (event.oldEvent) {
		_event.oldEvent = event.oldEvent
	}

	return _event
}

function setEventCallbackFields(targetEvent: ComponentEvent, sourceEvent: ComponentEvent) {
	targetEvent.on_success = sourceEvent.on_success
	targetEvent.on_error = sourceEvent.on_error

	if (sourceEvent.on_success === "message") {
		if (sourceEvent.success_message) {
			targetEvent.success_message = sourceEvent.success_message
		}
	} else if (sourceEvent.on_success === "script") {
		targetEvent.on_success_script = sourceEvent.on_success_script
	}

	if (sourceEvent.on_error === "message") {
		if (sourceEvent.error_message) {
			targetEvent.error_message = sourceEvent.error_message
		}
	} else if (sourceEvent.on_error === "script") {
		targetEvent.on_error_script = sourceEvent.on_error_script
	}
}

const deleteEvent = async (event: ComponentEvent) => {
	const confirmed = await confirm(
		`Are you sure you want to delete the ${event.event} event on ${props.block?.componentName}?`,
	)
	if (confirmed) {
		try {
			props.block?.removeEvent(event.event)
			toast.success(`Event ${event.event} deleted successfully`)
		} catch (error) {
			toast.error(`Failed to delete the event ${event.event}: ${error}`)
		}
	}
}

const openEvent = (event: ComponentEvent) => {
	newEvent.value = {
		...event,
		isEditing: true,
		oldEvent: event.event,
	}
	showAddEventDialog.value = true
}

const saveEvent = (event: ComponentEvent) => {
	const { isEditing } = event
	event = getEvent(event)
	if (isEditing) {
		props.block?.updateEvent(event)
		toast.success("Event updated successfully")
	} else {
		props.block?.addEvent(event)
	}
	if (event.action !== "Run Script") {
		showAddEventDialog.value = false
	}
}

const getEventMenu = (event: ComponentEvent) => {
	return [
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			onClick: () => deleteEvent(event),
		},
	]
}

function getScriptDescription(eventName: string): string {
	let docsLink = ""
	if (props.block && componentEvents.value.includes(eventName)) {
		const componentSlug = props.block.componentName.toLowerCase()
		docsLink = `https://ui.frappe.io/docs/components/${componentSlug}#emit-events`
	}
	let docs = `Define a ${getCodeBlock(
		"handleEvent",
	)} function to access event arguments with named parameters:<br><br>`

	if (docsLink) {
		docs += `
			<b>Example:</b> The ${getCodeBlock("change")} event on DatePicker emits the selected date:<br>
			${getCodeBlock(
				"function handleEvent(date) { myVar.value = date }",
			)} <br><br>Refer to the <a class="underline" href="${docsLink}" target="_blank">${[
				props.block?.componentName,
			]} documentation</a> to see what arguments are emitted for ${eventName} event
		`
	} else {
		docs += `
			<b>Example:</b> For a ${getCodeBlock("click")} event:<br>
			${getCodeBlock("function handleEvent(mouseEvent) { console.log(mouseEvent) }")}
		`
	}
	return docs
}

function getCodeBlock(string: string): string {
	return `<span class="font-mono font-medium">${string}</span>`
}
</script>
