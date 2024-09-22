<template>
	<div class="flex flex-col gap-5">
		<div class="flex flex-col gap-2">
			<div v-for="resource in store.resources" :key="resource.resourceName">
				<span class="text-xs text-gray-700"> {{ resource.resourceName }}</span>
				<pre>{{ resource }}</pre>
			</div>
		</div>

		<Button @click="showAddResourceDialog = true">Add Resource</Button>

		<Dialog
			v-model="showAddResourceDialog"
			:options="{
				title: 'Add Resource',
				size: 'lg',
				actions: [
					{
						label: 'Add',
						variant: 'solid',
						onClick: () => {
							store.addResource(newResource)
							showAddResourceDialog = false
						},
					},
				],
			}"
		>
			<template #body-content>
				<div class="flex flex-col gap-3">
					<FormControl label="Resource Title" v-model="newResource.resourceName" autocomplete="off" />
					<FormControl
						label="Resource Type"
						type="select"
						:options="['List Resource', 'Document Resource', 'API Resource']"
						autocomplete="off"
						v-model="newResource.resourceType"
					/>
					<template v-if="newResource.resource_type === 'API Resource'">
						<FormControl label="URL" v-model="newResource.url" />
						<FormControl
							label="Method"
							type="select"
							:options="['GET', 'POST', 'PUT', 'DELETE']"
							v-model="newResource.method"
						/>
					</template>
					<template v-else>
						<Link doctype="DocType" label="Document Type" v-model="newResource.doctype" />
						<Link
							v-if="newResource.resource_type === 'Document Resource' && newResource.doctype"
							:doctype="newResource.doctype"
							label="Document Name"
							v-model="newResource.name"
						/>
						<FormControl
							v-if="newResource.doctype"
							type="autocomplete"
							label="Fields"
							:placeholder="`Select fields from ${newResource.doctype}`"
							v-model="newResource.fields"
							:options="doctypeFields"
							:multiple="true"
						/>
					</template>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref, watch } from "vue"
import { createResource } from "frappe-ui"
import Link from "@/components/Link.vue"
import FormControl from "frappe-ui/src/components/FormControl.vue"
import useStore from "@/store"

const store = useStore()

const showAddResourceDialog = ref(false)
const newResource = ref({
	resourceName: "",
	resourceType: "",
	url: "",
	method: "GET",
	doctype: "",
	fields: [],
	name: "",
})
const doctypeFields = ref([])

watch(
	() => newResource.value.doctype,
	async () => {
		if (newResource.value.doctype) {
			doctypeFields.value = await getDoctypeFields()
		}
	},
)

async function getDoctypeFields() {
	const doctypeFields = createResource({
		url: "studio.api.get_doctype_fields",
		params: { doctype: newResource.value.doctype },
		transform: (data) => {
			return data.map((field) => {
				return {
					label: field.fieldname,
					value: field.fieldname,
				}
			})
		},
	})
	await doctypeFields.reload()
	return doctypeFields.data
}
</script>
