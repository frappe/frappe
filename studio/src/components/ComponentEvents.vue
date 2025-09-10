<template>
	<div class="flex flex-col p-4">
		<div v-if="block" class="flex flex-col gap-3">
			<div class="flex w-full flex-col space-y-1" v-if="!isObjectEmpty(block?.componentEvents)">
				<div
					v-for="(event, name) in block?.componentEvents"
					:key="name"
					class="group/event flex w-full cursor-pointer flex-row items-center justify-between gap-2 rounded border-[1px] border-gray-300 px-2 py-2"
				>
					<div class="gap-1 self-center truncate text-base text-gray-700">{{ name }}</div>
					<div
						class="invisible ml-auto self-start text-gray-600 group-hover/event:visible has-[.active-item]:visible"
					>
						<Dropdown :options="getEventMenu(event)" trigger="click">
							<template v-slot="{ open }">
								<button
									class="flex cursor-pointer items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
									:class="open ? 'active-item' : ''"
								>
									<FeatherIcon name="more-horizontal" class="h-3 w-3" />
								</button>
							</template>
						</Dropdown>
					</div>
				</div>
			</div>

			<EmptyState v-else message="No events added" />

			<Button class="mt-2" icon-left="plus" @click="showAddEventDialog = true">Add Event</Button>
			<Dialog
				v-model="showAddEventDialog"
				:options="{
					title: newEvent.isEditing ? 'Edit Event' : 'Add Event',
					size: '3xl',
					actions: [
						{
							label: newEvent.isEditing ? 'Update' : 'Add',
							variant: 'solid',
							onClick: () => {
								const event = getEvent(newEvent)
								if (newEvent.isEditing) {
									block?.updateEvent(event)
								} else {
									if (newEvent.page) {
										newEvent.page = store.getAppPageRoute(newEvent.page)
									}
									block?.addEvent(event)
								}
								showAddEventDialog = false
							},
						},
					],
				}"
				@after-leave="newEvent = { ...emptyEvent, fields: [], isEditing: false }"
			>
				<template #body-content>
					<div class="flex flex-col gap-3">
						<FormControl
							type="autocomplete"
							:options="eventOptions"
							label="Event"
							:modelValue="newEvent.event"
							@update:modelValue="(val: SelectOption) => (newEvent.event = val.value)"
						/>
						<FormControl
							type="autocomplete"
							:options="Object.keys(actions)"
							label="Action"
							:modelValue="newEvent.action"
							@update:modelValue="(val: SelectOption) => (newEvent.action = val.value as Actions)"
						/>
						<component
							v-for="control in actionControls"
							:key="control.component.name"
							:is="control.component"
							v-bind="control.getProps()"
							v-on="control.events || {}"
							:class="control.class || ''"
						/>

						<template v-if="['Insert a Document', 'Call API'].includes(newEvent.action)">
							<!-- Success Section -->
							<div class="border-t border-gray-200 pt-4">
								<div class="mb-3">
									<h3 class="mb-2 text-sm font-medium text-gray-900">On Success</h3>
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
										(context: CompletionContext) => getCompletions(context, props.block?.getCompletions())
									"
									:emitOnChange="true"
									:modelValue="newEvent.on_success_script?.toString()"
									@update:modelValue="(val: string) => (newEvent.on_success_script = val)"
								/>
							</div>

							<!-- Failure Section -->
							<div class="border-t border-gray-200 pt-4">
								<div class="mb-3">
									<h3 class="mb-2 text-sm font-medium text-gray-900">On Failure</h3>
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
										(context: CompletionContext) => getCompletions(context, props.block?.getCompletions())
									"
									:emitOnChange="true"
									:modelValue="newEvent.on_error_script?.toString()"
									@update:modelValue="(val: string) => (newEvent.on_error_script = val)"
								/>
							</div>
						</template>
					</div>
				</template>
			</Dialog>
		</div>

		<EmptyState v-else message="Select a block to edit events" />
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch, resolveComponent } from "vue"
import { FormControl, createResource, Dialog, TabButtons } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import Block from "@/utils/block"
import EmptyState from "@/components/EmptyState.vue"

import { isObjectEmpty, confirm } from "@/utils/helpers"

import type { SelectOption } from "@/types"
import type { Actions, ActionConfigurations, ComponentEvent } from "@/types/ComponentEvent"
import Link from "@/components/Link.vue"
import Grid from "@/components/Grid.vue"
import Code from "@/components/Code.vue"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { DocTypeField } from "@/types"
import { toast } from "vue-sonner"
import type { CompletionContext } from "@codemirror/autocomplete"

const props = defineProps<{
	block?: Block
}>()
const store = useStudioStore()
const getCompletions = useStudioCompletions(true)

const showAddEventDialog = ref(false)
const emptyEvent: ComponentEvent = {
	event: "click",
	action: "Run Script",
	page: "",
	url: "",
	api_endpoint: "",
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
		...getComponentEvents(props.block?.componentName),
		"click",
		"change",
		"focus",
		"blur",
		"submit",
		"keydown",
		"keyup",
		"keypress",
	]
})

function getComponentEvents(name: string) {
	const component = resolveComponent(name)
	if (typeof component === "string" || !component) {
		return []
	}
	return component?.emits || []
}

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
			doctypeFields.value.forEach((field) => {
				newEvent.value.fields?.push({
					field: field.value,
					value: Object.keys(store.variables).includes(field.value) ? field.value : "",
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
					language: "javascript",
					modelValue: newEvent.value.script,
					height: "400px",
					maxHeight: "400px",
					emitOnChange: true,
					completions: (context: CompletionContext) => getCompletions(context, props.block?.getCompletions()),
				}
			},
			events: {
				"update:modelValue": (val: any) => {
					newEvent.value.script = val
				},
			},
		},
	],
	"Call API": [
		{
			component: FormControl,
			getProps: () => {
				return {
					type: "input",
					label: "API Endpoint",
					modelValue: newEvent.value.api_endpoint,
					autocomplete: "off",
				}
			},
			events: {
				"update:modelValue": (val: string) => {
					newEvent.value.api_endpoint = val
				},
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
							options: store.variableOptions,
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
	"Switch App Page": [
		{
			component: FormControl,
			getProps: () => {
				return {
					type: "autocomplete",
					options: Object.values(store.appPages || [])?.map((page) => {
						return {
							value: page.name,
							label: page.page_title,
						}
					}),
					label: "Page",
					modelValue: newEvent.value.page,
				}
			},
			events: {
				"update:modelValue": (val: SelectOption) => {
					newEvent.value.page = val.value
				},
			},
		},
	],
	"Open Webpage": [
		{
			component: FormControl,
			getProps: () => {
				return {
					type: "input",
					label: "URL",
					modelValue: newEvent.value.url,
				}
			},
			events: {
				"update:modelValue": (val: string) => {
					newEvent.value.url = val
				},
			},
		},
	],
}

const actionControls = computed(() => {
	return actions[newEvent.value.action] || []
})

function getFnBoilerplate(event: "success" | "error") {
	if (event === "success") {
		return "function onSuccess(data) { \n\t \n}"
	} else {
		return "function onError(error) { \n\t \n}"
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
	} else if (event.action === "Call API") {
		_event.api_endpoint = event.api_endpoint
		setEventCallbackFields(_event, event)
	} else if (event.action === "Insert a Document") {
		_event.doctype = event.doctype
		_event.fields = event.fields
		setEventCallbackFields(_event, event)
	} else if (event.action === "Switch App Page") {
		if (event.page) {
			_event.page = store.getAppPageRoute(event.page)
		}
	} else if (event.action === "Open Webpage") {
		_event.url = event.url
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

// Event Menu
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

const getEventMenu = (event: ComponentEvent) => {
	return [
		{
			label: "Edit",
			icon: "edit",
			onClick: async () => {
				newEvent.value = { ...event, isEditing: true, oldEvent: event.event }
				showAddEventDialog.value = true
			},
		},
		{
			label: "Delete",
			icon: "trash",
			onClick: () => deleteEvent(event),
		},
	]
}
</script>
