<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: 'Add Fields from DocType',
			size: '3xl',
		}"
		@after-leave="
			() => {
				formMeta.doctype = ''
				formMeta.fields = []
			}
		"
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
					label="Field to component mapping"
					:columns="[
						{ label: 'Label', fieldname: 'label', fieldtype: 'Data' },
						{ label: 'Fieldname', fieldname: 'fieldname', fieldtype: 'Data' },
						{
							label: 'Fieldtype',
							fieldname: 'fieldtype',
							fieldtype: 'Select',
							options: fieldTypes,
							onChange: (_value: string, index: number) => {
								const { componentName, componentType } = getComponentFromFieldType(_value)
								formMeta.fields[index].componentName = componentName
								formMeta.fields[index].componentType = componentType
							},
						},
						{
							label: 'Component Name',
							fieldname: 'componentName',
							fieldtype: 'Select',
							options: components.names,
							width: 3,
						},
						{ label: 'Component Type', fieldname: 'componentType', fieldtype: 'Data', width: 3 },
					]"
					v-model:rows="formMeta.fields"
					:showDeleteBtn="true"
				/>
			</div>
		</template>

		<template #actions>
			<Button variant="solid" label="Add Fields" @click="() => addFields()" class="w-full" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { createResource, Dialog } from "frappe-ui"
import Block from "@/utils/block"
import { getComponentBlock } from "@/utils/helpers"
import type { DocTypeField } from "@/types"
import components from "@/data/components"
import Link from "@/components/Link.vue"
import Grid from "@/components/Grid.vue"
import { toast } from "vue-sonner"

const props = defineProps<{
	block?: Block | null
}>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const formMeta = ref({
	doctype: "",
	fields: [],
})

const doctypeFields = ref([])
async function setDoctypeFields(doctype: string) {
	const fields = createResource({
		url: "studio.api.get_doctype_fields",
		params: { doctype: doctype },
		transform: (data: DocTypeField[]) => {
			return data.map((field) => {
				const { componentName, componentType } = getComponentFromFieldType(field.fieldtype)
				return {
					...field,
					componentName: componentName,
					componentType: componentType,
				}
			})
		},
	})
	await fields.reload()
	doctypeFields.value = fields.data
}

watch(
	() => formMeta.value?.doctype,
	(doctype) => {
		if (!doctype) return
		setDoctypeFields(doctype)
	},
)

const fieldTypes = ["Data", "Link", "Select", "Check", "Date", "Datetime", "Markdown Editor", "Small Text"]

const getComponentFromFieldType = (fieldType: string) => {
	switch (fieldType) {
		case "Data":
			return { componentName: "FormControl", componentType: "text" }
		case "Small Text":
			return { componentName: "FormControl", componentType: "textarea" }
		case "Link":
			return { componentName: "Link", componentType: "Link" }
		case "Select":
			return { componentName: "FormControl", componentType: "select" }
		case "Check":
			return { componentName: "FormControl", componentType: "checkbox" }
		case "Date":
			return { componentName: "FormControl", componentType: "date" }
		case "Datetime":
			return { componentName: "FormControl", componentType: "datetime-local" }
		case "Markdown Editor":
			return { componentName: "MarkdownEditor", componentType: "MarkdownEditor" }
		default:
			return { componentName: "FormControl", componentType: "text" }
	}
}

const addFields = () => {
	if (!props.block) return

	formMeta.value.fields.forEach((field) => {
		const newBlock = getComponentBlock(field.componentName)
		newBlock?.setProp("label", field.label)
		if (field.componentName === "FormControl") {
			newBlock?.setProp("type", field.componentType)
		}
		props.block?.addChild(newBlock)
	})

	showDialog.value = false
	toast.success(`${formMeta.value.doctype} fields added to ${props.block.componentId}`)
}
</script>
