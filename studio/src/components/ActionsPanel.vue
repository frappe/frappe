<template>
	<div class="flex flex-col p-4">
		<div class="flex flex-col gap-3">
			<div class="flex w-full flex-col space-y-1" v-if="!isObjectEmpty(store.actions)">
				<div v-for="(action, name) in store.actions" :key="name" class="flex w-full flex-row justify-between">
					<div
						class="group flex w-full cursor-pointer items-center justify-between gap-2 truncate rounded border-[1px] border-gray-300 px-2 py-2 transition duration-300 ease-in-out"
					>
						<div class="flex items-center gap-1 truncate text-base text-gray-700">{{ name }}</div>
						<FeatherIcon
							name="trash"
							class="invisible h-3 w-3 cursor-pointer group-hover:visible"
							@click="store.removeAction(action)"
						/>
					</div>
				</div>
			</div>

			<EmptyState v-else message="No actions added" />

			<Button class="mt-2" icon-left="plus" @click="showAddActionDialog = true">Add Action</Button>
			<Dialog
				v-model="showAddActionDialog"
				:options="{
					title: 'Add Action',
					size: 'lg',
					actions: [
						{
							label: 'Add',
							variant: 'solid',
							onClick: () => {
								store.addAction(newAction)
								showAddActionDialog = false
							},
						},
					],
				}"
				@after-leave="newAction = { ...emptyAction }"
			>
				<template #body-content>
					<div class="flex flex-col gap-3">
						<FormControl
							type="autocomplete"
							:options="eventOptions"
							label="Event"
							:modelValue="newAction.event"
							@update:modelValue="(val: SelectOption) => (newAction.event = val.value)"
						/>
						<FormControl
							type="autocomplete"
							:options="Object.keys(actions)"
							label="Action"
							:modelValue="newAction.action"
							@update:modelValue="(val: SelectOption) => (newAction.action = val.value)"
						/>
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
	</div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import { FormControl } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import EmptyState from "@/components/EmptyState.vue"

import { isObjectEmpty } from "@/utils/helpers"

const store = useStudioStore()

const showAddActionDialog = ref(false)
const emptyAction = {
	event: "On Page Load",
	action: "",
	page: {},
	url: "",
}
const newAction = ref({ ...emptyAction })

const eventOptions = computed(() => {
	return ["On Page Load"]
})

const actions = {
	"Fetch Data": [
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
					modelValue: newAction.value.page,
				}
			},
			events: {
				"update:modelValue": (val: SelectOption) => {
					newAction.value.page = val
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
					label: "URL",
					modelValue: newAction.value.url,
				}
			},
			events: {
				"update:modelValue": (val: string) => {
					newAction.value.url = val
				},
			},
		},
	],
}

const actionControls = computed(() => {
	return actions[newAction.value.action] || []
})
</script>
