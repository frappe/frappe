<template>
	<Dialog class="pb-0" v-model="show" :options="{ size: 'sm' }">
		<template #body>
			<div class="flex flex-col gap-4 p-5">
				<div class="flex items-center justify-between">
					<div class="text-md font-semibold text-gray-900">{{ mode }}</div>
					<FeatherIcon name="x" class="h-4 cursor-pointer" @click="show = false" />
				</div>
				<div v-if="mode == 'Save View As'">
					<div class="flex flex-col gap-4">
						<FormControl
							:type="'text'"
							size="md"
							variant="subtle"
							placeholder="View Name"
							v-model="newViewName"
						/>
						<Button variant="solid" label="Save" @click="createView">
							<template #prefix>
								<FeatherIcon name="save" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>
				<div v-else-if="mode == 'Save'">
					<div class="flex flex-col gap-4">
						<FormControl
							:type="'text'"
							size="md"
							variant="subtle"
							placeholder="View Name"
							v-model="config_settings.data.label"
						/>
						<Button variant="solid" label="Update" @click="renameView">
							<template #prefix>
								<FeatherIcon name="save" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>
				<div v-else>
					<div class="flex flex-col gap-4">
						<div class="text-base">Are you sure you want to delete this view?</div>
						<Button variant="outline" theme="red" label="Delete" @click="deleteView">
							<template #prefix>
								<FeatherIcon name="trash" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, defineModel } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Dialog, FormControl, FeatherIcon, Button, createResource, call } from "frappe-ui"

import { config_name, config_settings } from "@/stores/view"

const show = defineModel()

const props = defineProps({
	listConfig: {
		type: Object,
		required: true,
	},
	queryFilters: {
		type: Object,
		required: true,
	},
	mode: {
		type: String,
		default: "Create",
	},
})

const route = useRoute()
const router = useRouter()

const newViewName = ref("")

const createConfigResource = createResource({
	url: "frappe.client.insert",
	method: "POST",
	makeParams: () => {
		return {
			doc: {
				doctype: "View Config",
				document_type: route.params.doctype,
				label: newViewName.value,
				columns: JSON.stringify(props.listConfig.columns),
				filters: JSON.stringify(props.queryFilters),
				sort_field: props.listConfig.sort[0],
				sort_order: props.listConfig.sort[1],
				custom: 1,
			},
		}
	},
})

const createView = async () => {
	show.value = false
	let doc = await createConfigResource.submit()
	await router.replace({ query: { view: doc.name } })
}

const deleteView = async () => {
	show.value = false
	await call("frappe.client.delete", { doctype: "View Config", name: config_name.value })
}

const renameView = async () => {
	show.value = false
	await call("frappe.client.set_value", {
		doctype: "View Config",
		name: config_name.value,
		fieldname: "label",
		value: config_settings.data.label,
	})
}
</script>
