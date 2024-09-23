<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: 'Add Resource',
			size: 'lg',
			actions: [
				{
					label: 'Add',
					variant: 'solid',
					onClick: () => {
						store.addResource(newResource)
						showDialog = false
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-3">
				<FormControl label="Resource Name" v-model="newResource.resourceName" autocomplete="off" />
				<FormControl
					label="Resource Type"
					type="select"
					:options="['List Resource', 'Document Resource', 'API Resource']"
					autocomplete="off"
					v-model="newResource.resourceType"
				/>
				<template v-if="newResource.resourceType === 'API Resource'">
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
						v-if="newResource.resourceType === 'Document Resource' && newResource.doctype"
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
</template>

<script setup>
import { ref, watch } from "vue"
import { createResource } from "frappe-ui"
import Link from "@/components/Link.vue"
import useStore from "@/store"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })
const store = useStore()

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
