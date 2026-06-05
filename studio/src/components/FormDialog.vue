<template>
	<Dialog
		v-model="showDialog"
		title="Add Fields from DocType"
		size="3xl"
		@after-leave="
			() => {
				formMeta.doctype = ''
				formMeta.fields = []
				formMeta.variant = undefined
			}
		"
	>
		<template #default>
			<div class="flex flex-col space-y-4">
				<Link label="Document Type" :required="true" doctype="DocType" v-model="formMeta.doctype" />
				<FormControl
					label="Fields"
					:required="true"
					type="multiselect"
					:placeholder="`Select fields from ${formMeta.doctype}`"
					v-model="formMeta.fields"
					:options="doctypeFields.data"
					:multiple="true"
				>
					<template #summary="{ selectedOptions, summary }">
						<template v-if="selectedOptions.length">
							{{ selectedOptions.map((o: SelectOption) => o.label).join(", ") }}
						</template>
						<template v-else>{{ summary }}</template>
					</template>
				</FormControl>
				<Grid
					label="Field to component mapping"
					:columns="[
						{ label: 'Label', fieldname: 'label', fieldtype: 'Data' },
						{ label: 'Fieldname', fieldname: 'fieldname', fieldtype: 'Data' },
						{
							label: 'Fieldtype',
							fieldname: 'fieldtype',
							fieldtype: 'Autocomplete',
							options: fieldTypes,
							onChange: (_value: string, index: number) => {
								const { componentName, componentType } = getComponentForField(_value)
								formMeta.fields[index].componentName = componentName
								formMeta.fields[index].componentType = componentType
							},
						},
						{
							label: 'Component Name',
							fieldname: 'componentName',
							fieldtype: 'Autocomplete',
							options: components.names,
							width: 3,
						},
						{ label: 'Component Type', fieldname: 'componentType', fieldtype: 'Data', width: 3 },
					]"
					v-model:rows="formMeta.fields"
					:showDeleteBtn="true"
				/>
				<FormControl
					v-if="showVariantField"
					label="Field Variant"
					type="select"
					:options="['subtle', 'outline']"
					v-model="formMeta.variant"
					description="Selected variant will be applied to all FormControl fields"
				/>
			</div>
		</template>

		<template #actions>
			<Button variant="solid" label="Add Fields" @click="() => addFields()" class="w-full" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { createResource, Dialog, FormControl } from "frappe-ui"
import Block from "@/utils/block"
import { getComponentBlock } from "@/utils/serializer"
import type { DocTypeField, SelectOption } from "@/types"
import components from "@/data/components"
import { Link } from "frappe-ui/frappe"
import Grid from "@/components/Grid.vue"
import { toast } from "frappe-ui"

const props = defineProps<{
	block?: Block | null
}>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })

type FormField = DocTypeField & {
	componentName: string
	componentType?: string
	name: string
}
const formMeta = ref<{
	doctype: string
	fields: FormField[]
	variant?: string
}>({
	doctype: "",
	fields: [],
})

const doctypeFields = createResource({
	url: "studio.api.get_doctype_fields",
	makeParams() {
		return { doctype: formMeta.value.doctype }
	},
	transform: (data: DocTypeField[]) => {
		return data.map((field) => {
			const { componentName, componentType } = getComponentForField(field)
			return {
				...field,
				value: field.fieldname,
				componentName: componentName,
				componentType: componentType,
				name: field.fieldname,
			}
		})
	},
})

watch(
	() => formMeta.value?.doctype,
	(doctype) => {
		if (!doctype) return
		doctypeFields.fetch()
	},
)

const showVariantField = computed(() => {
	return formMeta.value.fields.some((field) => field.componentName === "FormControl")
})

const fieldTypes = [
	"Data",
	"Int",
	"Float",
	"Password",
	"Text",
	"Small Text",
	"Long Text",
	"Select",
	"Check",
	"Date",
	"Datetime",
	"Time",
	"Link",
	"Text Editor",
	"Rating",
]

const getComponentForField = (arg?: DocTypeField | string) => {
	const fieldType = typeof arg === "string" ? arg : arg?.fieldtype
	const field = typeof arg === "object" ? arg : null

	switch (fieldType) {
		case "Data":
			if (field?.options === "Email") {
				return { componentName: "FormControl", componentType: "email" }
			}
			return { componentName: "FormControl", componentType: "text" }
		case "Int":
		case "Float":
			return { componentName: "FormControl", componentType: "number" }
		case "Password":
			return { componentName: "FormControl", componentType: "password" }
		case "Text":
		case "Small Text":
		case "Long Text":
			return { componentName: "FormControl", componentType: "textarea" }
		case "Select":
			return { componentName: "FormControl", componentType: "select" }
		case "Check":
			return { componentName: "FormControl", componentType: "checkbox" }
		case "Date":
			return { componentName: "FormControl", componentType: "date" }
		case "Datetime":
			return { componentName: "FormControl", componentType: "datetime-local" }
		case "Time":
			return { componentName: "FormControl", componentType: "time" }
		case "Link":
			return { componentName: "Link" }
		case "Text Editor":
			return { componentName: "TextEditor" }
		case "Rating":
			return { componentName: "Rating" }
		default:
			return { componentName: "FormControl", componentType: "text" }
	}
}

const addFields = () => {
	if (!props.block) return

	formMeta.value.fields.forEach((field: FormField) => {
		const newBlock = getComponentBlock(field.componentName)
		if (field.componentName === "FormControl") {
			newBlock?.setProp("type", field.componentType)
			if (formMeta.value.variant) {
				newBlock?.setProp("variant", formMeta.value.variant)
			}
			if (field.description) {
				newBlock?.setProp("description", field.description)
			}
		}
		if (field.label) {
			newBlock?.setProp("label", field.label)
			newBlock?.setProp("placeholder", "")
		}
		if (field.reqd) {
			newBlock?.setProp("required", true)
		}
		if (field.read_only) {
			newBlock?.setProp("disabled", true)
		}
		if (field.options) {
			if (field.componentType === "select") {
				newBlock?.setProp("options", field.options.split("\n"))
			} else if (field.componentType === "Link") {
				newBlock?.setProp("doctype", field.options)
			}
		}
		props.block?.addChild(newBlock)
	})

	showDialog.value = false
	toast.success(`${formMeta.value.doctype} fields added to ${props.block.componentId}`)
}
</script>
