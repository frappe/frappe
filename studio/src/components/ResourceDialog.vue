<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: resource?.name ? 'Edit Data Source' : 'Add Data Source',
			size: '2xl',
			actions: [
				{
					label: resource?.name ? 'Save' : 'Add',
					variant: 'solid',
					onClick: () => {
						if (resource?.name) {
							emit('editResource', newResource)
						} else {
							emit('addResource', newResource)
						}
					},
				},
			],
		}"
		@after-leave="newResource = { ...emptyResource }"
	>
		<template #body-content>
			<div class="flex flex-col space-y-4">
				<FormControl
					label="New or Existing"
					v-if="!resource?.name"
					type="select"
					:options="['New Data Source', 'Existing Data Source']"
					autocomplete="off"
					v-model="newResource.source"
				/>
				<Link
					label="Data Source"
					v-if="newResource.source === 'Existing Data Source'"
					:required="true"
					doctype="Studio Resource"
					placeholder="Select Data Source"
					v-model="newResource.name"
				/>

				<template v-else>
					<FormControl
						label="Data Source Name"
						:required="true"
						v-model="newResource.resource_name"
						autocomplete="off"
					/>
					<FormControl
						label="Type"
						type="select"
						:options="['Document List', 'Document', 'API Resource']"
						autocomplete="off"
						v-model="newResource.resource_type"
					/>

					<!-- API Resource -->
					<template v-if="newResource.resource_type === 'API Resource'">
						<FormControl label="URL" v-model="newResource.url" :required="true" />
						<FormControl
							label="Method"
							type="select"
							:options="['GET', 'POST', 'PUT', 'DELETE']"
							v-model="newResource.method"
						/>
					</template>

					<Link
						v-else
						label="Document Type"
						:required="true"
						doctype="DocType"
						v-model="newResource.document_type"
					/>

					<!-- Document List -->
					<template v-if="newResource.resource_type === 'Document List' && newResource.document_type">
						<FormControl
							label="Fields"
							:required="true"
							type="autocomplete"
							:placeholder="`Select fields from ${newResource.document_type}`"
							v-model="newResource.fields"
							:options="doctypeFields"
							:multiple="true"
						/>
						<Filters label="Filters" v-model="newResource.filters" :docfields="filterFields" />
					</template>

					<!-- Document -->
					<template v-if="newResource.resource_type === 'Document' && newResource.document_type">
						<Link
							label="Document Name"
							v-if="!newResource.fetch_document_using_filters"
							:required="true"
							:doctype="newResource.document_type"
							v-model="newResource.document_name"
						/>

						<div class="flex w-full flex-row gap-1.5">
							<FormControl size="sm" type="checkbox" v-model="newResource.fetch_document_using_filters" />
							<InputLabel class="max-w-full">Dynamically fetch document using filters</InputLabel>
						</div>

						<Filters
							v-if="newResource.fetch_document_using_filters"
							v-model="newResource.filters"
							:docfields="filterFields"
						/>

						<FormControl
							label="Whitelisted Methods"
							type="autocomplete"
							v-model="newResource.whitelisted_methods"
							:options="whitelistedMethods"
							:multiple="true"
						/>
					</template>

					<!-- Transform Results for any Resource Type -->
					<div class="flex flex-row gap-1.5">
						<FormControl size="sm" type="checkbox" v-model="newResource.transform_results" />
						<InputLabel>Transform Results</InputLabel>
					</div>

					<CodeEditor
						v-if="newResource.transform_results"
						v-model="newResource.transform"
						type="JavaScript"
						height="150px"
						:showLineNumbers="true"
					/>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { createResource } from "frappe-ui"
import Link from "@/components/Link.vue"
import CodeEditor from "@/components/CodeEditor.vue"
import InputLabel from "@/components/InputLabel.vue"
import Filters from "@/components/Filters.vue"

import { DocTypeField } from "@/types"
import { NewResource, ResourceType, Resource } from "@/types/Studio/StudioResource"
import { isObjectEmpty } from "@/utils/helpers"

const props = defineProps<{
	resource?: Resource | null
}>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })
const emit = defineEmits(["addResource", "editResource"])

const emptyResource: NewResource = {
	// source
	source: "New Data Source",
	// config
	resource_name: "",
	resource_type: "Document List",
	url: "",
	method: "GET",
	document_type: "",
	document_name: "",
	fetch_document_using_filters: false,
	fields: [],
	filters: {},
	whitelisted_methods: [],
	transform_results: false,
	transform: "",
}

const newResource = ref<NewResource | Resource>({ ...emptyResource })
watch(
	() => props.resource,
	async () => {
		if (props.resource?.name) {
			newResource.value = await getResourceToEdit()
		} else {
			newResource.value = { ...emptyResource }
		}
	},
	{ immediate: true },
)

async function getResourceToEdit() {
	const filters = getParsedFilters(props.resource?.filters)
	if (props.resource?.document_type) {
		await setDoctypeFields(props.resource.document_type)
		await setWhitelistedMethods(props.resource.document_type)
	}

	return {
		...props.resource,
		source: "",
		name: props.resource?.name,
		resource_name: props.resource?.resource_name,
		filters: filters,
		fields: JSON.parse(props.resource?.fields || "[]"),
		whitelisted_methods: JSON.parse(props.resource?.whitelisted_methods || "[]"),
	} as Resource
}

function getParsedFilters(filters: string | object | undefined) {
	if (filters && typeof filters === "string") {
		filters = JSON.parse(filters)
		if (isObjectEmpty(filters as object)) {
			return {}
		}
	}
	return filters
}

const doctypeFields = ref([])
const filterFields = ref<DocTypeField[]>([])
const whitelistedMethods = ref([])

const getTransformFnBoilerplate = (resource_type: ResourceType) => {
	if (resource_type == "Document") {
		return "function transform(doc) { \n\treturn doc; \n}"
	} else {
		return "function transform(data) { \n\treturn data; \n}"
	}
}

watch(
	() => newResource.value?.document_type,
	(doctype) => {
		if (!doctype) return
		setDoctypeFields(doctype)
		setWhitelistedMethods(doctype)
	},
)

watch(
	() => newResource.value?.resource_type,
	(resource_type) => {
		if (!resource_type) return
		newResource.value.transform = getTransformFnBoilerplate(resource_type)
	},
)

async function setDoctypeFields(doctype: string) {
	const fields = createResource({
		url: "studio.api.get_doctype_fields",
		params: { doctype: doctype },
		transform: (data: DocTypeField[]) => {
			filterFields.value = data
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
}

async function setWhitelistedMethods(doctype: string) {
	const methods = createResource({
		url: "studio.api.get_whitelisted_methods",
		params: { doctype: doctype },
		transform: (data: string[]) => {
			return data.map((method) => {
				return {
					label: method,
					value: method,
				}
			})
		},
	})
	await methods.reload()
	whitelistedMethods.value = methods.data
}
</script>
