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
						emit('addResource', newResource)
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-3">
				<FormControl
					label="New or Existing"
					type="select"
					:options="['New Resource', 'Existing Resource']"
					autocomplete="off"
					v-model="newResource.source"
				/>
				<Link
					v-if="newResource.source === 'Existing Resource'"
					doctype="Studio Resource"
					label="Resource"
					v-model="newResource.name"
				/>

				<template v-else>
					<FormControl label="Resource Name" v-model="newResource.name" autocomplete="off" />
					<FormControl
						label="Resource Type"
						type="select"
						:options="['List Resource', 'Document Resource', 'API Resource']"
						autocomplete="off"
						v-model="newResource.resource_type"
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
						<Link doctype="DocType" label="Document Type" v-model="newResource.document_type" />
						<Link
							v-if="newResource.resource_type === 'Document Resource' && newResource.document_type"
							:doctype="newResource.document_type"
							label="Document Name"
							v-model="newResource.document_name"
						/>
						<FormControl
							v-if="newResource.resource_type === 'List Resource' && newResource.document_type"
							type="autocomplete"
							label="Fields"
							:placeholder="`Select fields from ${newResource.document_type}`"
							v-model="newResource.fields"
							:options="doctypeFields"
							:multiple="true"
						/>
					</template>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, watch } from "vue"
import { createResource } from "frappe-ui"
import Link from "@/components/Link.vue"
import FormControl from "frappe-ui/src/components/FormControl.vue"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })
const emit = defineEmits(["addResource"])

const newResource = ref({
	// source
	source: "New Resource",
	// config
	name: "",
	resource_type: "",
	url: "",
	method: "GET",
	document_type: "",
	document_name: "",
	fields: [],
})
const doctypeFields = ref([])

watch(
	() => newResource.value.document_type,
	async () => {
		if (newResource.value.document_type) {
			doctypeFields.value = await getDoctypeFields()
		}
	},
)

async function getDoctypeFields() {
	const doctypeFields = createResource({
		url: "studio.api.get_doctype_fields",
		params: { doctype: newResource.value.document_type },
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
