<template>
	<div class="flex flex-col p-4">
		<div v-if="block" class="flex flex-col gap-3">
			<div class="flex w-full flex-col space-y-1" v-if="!isObjectEmpty(block?.componentEvents)">
				<div
					v-for="(event, name) in block?.componentEvents"
					:key="name"
					class="flex w-full flex-row justify-between"
				>
					<div
						class="group flex w-full cursor-pointer items-center justify-between gap-2 truncate rounded border-[1px] border-gray-300 px-2 py-2 transition duration-300 ease-in-out"
					>
						<div class="flex items-center gap-1 truncate text-base text-gray-700">{{ name }}</div>
						<FeatherIcon
							name="trash"
							class="invisible h-3 w-3 cursor-pointer group-hover:visible"
							@click="block.removeEvent(event)"
						/>
					</div>
				</div>
			</div>

			<EmptyState v-else message="No events added" />

			<Button class="mt-2" icon-left="plus" @click="showAddEventDialog = true">Add Event</Button>
			<Dialog
				v-model="showAddEventDialog"
				:options="{
					title: 'Add Event',
					size: 'lg',
					actions: [
						{
							label: 'Add',
							variant: 'solid',
							onClick: () => {
								block?.addEvent(newEvent)
								showAddEventDialog = false
							},
						},
					],
				}"
				@after-leave="newEvent = { ...emptyEvent }"
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

						<template v-if="newEvent.action === 'Insert a Document'">
							<Link label="Document Type" :required="true" doctype="DocType" v-model="newEvent.doctype" />
							<Grid
								label="Fields"
								:columns="[
									{ label: 'Field', fieldname: 'field', fieldtype: 'select', options: doctypeFields },
									{
										label: 'Variable',
										fieldname: 'value',
										fieldtype: 'select',
										options: Object.keys(store.variables),
									},
								]"
								v-model:rows="newEvent.fields"
								:showDeleteBtn="true"
							/>
						</template>

						<component
							v-for="control in actionControls"
							:key="control.component.name"
							:is="control.component"
							v-bind="control.getProps()"
							v-on="control.events || {}"
						/>
					</div>
				</template>
			</Dialog>
		</div>

		<EmptyState v-else message="Select a block to edit events" />
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { FormControl, createResource } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import Block from "@/utils/block"
import EmptyState from "@/components/EmptyState.vue"
import Link from "@/components/Link.vue"

import { isObjectEmpty } from "@/utils/helpers"
import { getComponentEvents } from "@/utils/components"

import { SelectOption } from "@/types"
import { Actions, ActionConfigurations, ComponentEvent } from "@/types/ComponentEvent"
import Grid from "./Grid.vue"
import { DocTypeField } from "@/types"

const props = defineProps<{
	block?: Block
}>()
const store = useStudioStore()

const showAddEventDialog = ref(false)
const emptyEvent: ComponentEvent = {
	event: "",
	action: "Call API",
	page: "",
	url: "",
	api_endpoint: "",
	// insert document
	doctype: "",
	fields: [],
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

const actions: ActionConfigurations = {
	"Switch App Page": [
		{
			component: FormControl,
			getProps: () => {
				return {
					type: "autocomplete",
					options: Object.values(store.appPages || [])?.map((page) => {
						return {
							value: page.page_name,
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
	"Insert a Document": [],
}

const doctypeFields = ref([])
watch(
	() => newEvent.value.doctype,
	async (value, oldValue) => {
		if (value === oldValue) return

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

		doctypeFields.value.forEach((field) => {
			newEvent.value.fields?.push({
				field: field.value,
				value: "",
				name: field.value,
			})
		})
	},
)

const actionControls = computed(() => {
	return actions[newEvent.value.action] || []
})
</script>
