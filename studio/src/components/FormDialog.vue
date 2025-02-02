<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: 'Add Fields from DocType',
			size: '2xl',
		}"
	>
		<template #body-content>
			<div class="flex flex-col space-y-4">
				<Link label="Document Type" :required="true" doctype="DocType" v-model="formMeta.doctype" />
				<FormControl
					label="Fields"
					:required="true"
					type="autocomplete"
					:placeholder="`Select fields from ${formMeta.doctype}`"
					v-model="formMeta.fields"
					:options="doctypeFields"
					:multiple="true"
				/>
				<Grid
					:columns="[
						{ label: 'Label', fieldname: 'label', fieldtype: 'Data' },
						{ label: 'Fieldname', fieldname: 'fieldname', fieldtype: 'Data' },
						{ label: 'Component', fieldname: 'component', fieldtype: 'Data' },
					]"
					v-model:rows="formMeta.fields"
					:showDeleteBtn="true"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { createResource } from "frappe-ui"
import Block from "@/utils/block"
import { DocTypeField } from "@/types"
import Link from "@/components/Link.vue"
import Grid from "@/components/Grid.vue"

const props = defineProps<{
	block?: Block | null
}>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const formMeta = ref({
	doctype: "",
	fields: [],
})

const doctypeFields = ref<DocTypeField[]>([])
const doctypeFieldOptions = ref([])
async function setDoctypeFields(doctype: string) {
	const fields = createResource({
		url: "studio.api.get_doctype_fields",
		params: { doctype: doctype },
		transform: (data: DocTypeField[]) => {
			doctypeFields.value = data
			return data.map((field) => {
				return {
					label: field.fieldname,
					value: field.fieldname,
				}
			})
		},
	})
	await fields.reload()
	doctypeFieldOptions.value = fields.data
}

watch(
	() => formMeta.value?.doctype,
	(doctype) => {
		if (!doctype) return
		setDoctypeFields(doctype)
	},
)
</script>
