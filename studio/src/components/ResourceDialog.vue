<template>
	<Dialog
		v-model="showDialog"
		:options="{
			title: resource?.resource_id ? 'Edit Data Source' : 'Add Data Source',
			size: '2xl',
		}"
		@after-leave="reset"
	>
		<template #body-content>
			<div class="flex flex-col space-y-4">
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
					<Grid
						label="Parameters"
						:columns="[
							{ label: 'Key', fieldname: 'key', fieldtype: 'Data' },
							{ label: 'Value', fieldname: 'value', fieldtype: 'Code', completions: getCompletions },
						]"
						:rows="Array.isArray(newResource.params) ? newResource.params : []"
						:showDeleteBtn="true"
						@update:rows="(val) => (newResource.params = val)"
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
						:options="doctypeFields.data"
						:multiple="true"
					/>
					<Filters label="Filters" v-model="newResource.filters" :docfields="filterFields" />
					<div class="flex w-full flex-row gap-2">
						<FormControl
							label="Sort Field"
							type="autocomplete"
							placeholder="Select sort field"
							:modelValue="newResource.sort_field"
							@update:modelValue="
								(val: SelectOption | string) => {
									if (typeof val === 'object') {
										newResource.sort_field = val?.value
									} else {
										newResource.sort_field = val || ''
									}
								}
							"
							:options="sortFields.data"
							class="w-full"
						/>
						<FormControl
							label="Sort Order"
							type="select"
							placeholder="Select sort order"
							v-model="newResource.sort_order"
							:options="['', 'ASC', 'DESC']"
							class="w-full"
						/>
					</div>
					<FormControl
						label="Limit"
						type="number"
						placeholder="Number of records to fetch (default: 20)"
						v-model="newResource.limit"
					/>
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

					<div class="flex w-full flex-row items-center gap-1.5">
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
						:options="whitelistedMethods.data"
						:multiple="true"
					/>
				</template>

				<!-- Transform Results for any Resource Type -->
				<div class="border-t border-gray-200 pt-4">
					<div class="mb-3">
						<div class="mb-2 flex items-center justify-between">
							<h3 class="text-sm font-medium text-gray-900">Transform Results</h3>
							<Button
								v-if="newResource.transform"
								variant="ghost"
								size="sm"
								icon="x"
								@click="() => (newResource.transform = '')"
							/>
						</div>

						<Code
							v-if="newResource.transform"
							v-model="newResource.transform"
							language="javascript"
							height="150px"
							:emitOnChange="true"
							:completions="getCompletions"
						/>
						<div class="flex flex-col items-center rounded-lg border border-gray-200 p-4" v-else>
							<span class="px-2 py-1 text-center text-sm leading-5 text-gray-500">
								Transform fetched data before use - reshape objects, format values or add extra properties
							</span>
							<button
								class="flex cursor-pointer items-center rounded p-1 text-gray-700 hover:bg-gray-300"
								@click="() => (newResource.transform = getTransformFnBoilerplate(newResource.resource_type))"
							>
								<FeatherIcon name="plus" class="h-3 w-3" />
								<span class="ml-1 text-sm">Add Script</span>
							</button>
						</div>
					</div>
				</div>

				<!-- Success Section -->
				<div class="border-t border-gray-200 pt-4">
					<div class="mb-3">
						<div class="mb-2 flex items-center justify-between">
							<h3 class="text-sm font-medium text-gray-900">On Success</h3>
							<Button
								v-if="newResource.on_success"
								variant="ghost"
								size="sm"
								icon="x"
								@click="() => (newResource.on_success = '')"
							/>
						</div>
						<Code
							v-if="newResource.on_success"
							:completions="(context: CompletionContext) => getEditorCompletions(context)"
							:emitOnChange="true"
							:modelValue="newResource.on_success?.toString()"
							@update:modelValue="(val: string) => (newResource.on_success = val)"
						/>
						<div class="flex flex-col items-center rounded-lg border border-gray-200 p-4" v-else>
							<span class="px-2 py-1 text-center text-sm leading-5 text-gray-500">
								Update variables or control other data sources everytime the data loads successfully
							</span>
							<button
								class="flex cursor-pointer items-center rounded p-1 text-gray-700 hover:bg-gray-300"
								@click="() => (newResource.on_success = getFnBoilerplate('success'))"
							>
								<FeatherIcon name="plus" class="h-3 w-3" />
								<span class="ml-1 text-sm">Add Script</span>
							</button>
						</div>
					</div>
				</div>

				<!-- Failure Section -->
				<div class="border-t border-gray-200 pt-4">
					<div class="mb-3">
						<div class="mb-2 flex items-center justify-between">
							<h3 class="text-sm font-medium text-gray-900">On Failure</h3>
							<Button
								v-if="newResource.on_error"
								variant="ghost"
								size="sm"
								icon="x"
								@click="() => (newResource.on_error = '')"
								title="Remove Script"
							/>
						</div>
						<Code
							v-if="newResource.on_error"
							:completions="(context: CompletionContext) => getEditorCompletions(context)"
							:emitOnChange="true"
							:modelValue="newResource.on_error?.toString()"
							@update:modelValue="(val: string) => (newResource.on_error = val)"
						/>
						<div class="flex flex-col items-center rounded border border-gray-200 p-4" v-else>
							<span class="px-2 py-1 text-sm text-gray-500">
								Handle errors gracefully with fallback logic or user alerts
							</span>
							<button
								class="flex cursor-pointer items-center rounded-lg p-1 text-gray-700 hover:bg-gray-300"
								@click="() => (newResource.on_error = getFnBoilerplate('error'))"
							>
								<FeatherIcon name="plus" class="h-3 w-3" />
								<span class="ml-1 text-sm">Add Script</span>
							</button>
						</div>
					</div>
				</div>
			</div>
		</template>

		<template #actions>
			<div class="space-y-1">
				<ErrorMessage class="mb-2" :message="errorMessage" />
				<Button
					variant="solid"
					:label="resource?.resource_id ? 'Save' : 'Add'"
					@click="
						() => {
							if (!areRequiredFieldsFilled()) return

							if (resource?.resource_id) {
								emit('editResource', newResource)
							} else {
								emit('addResource', newResource)
							}
						}
					"
					class="w-full"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { createResource, Dialog, FormControl } from "frappe-ui"
import { Link } from "frappe-ui/frappe"
import Code from "@/components/Code.vue"
import InputLabel from "@/components/InputLabel.vue"
import Filters from "@/components/Filters.vue"
import Grid from "@/components/Grid.vue"

import type { DocTypeField, SelectOption } from "@/types"
import type { ResourceType, Resource } from "@/types/Studio/StudioResource"
import { getParamsArray, isObjectEmpty } from "@/utils/helpers"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import type { CompletionContext } from "@codemirror/autocomplete"

const props = defineProps<{
	resource?: Resource | null
}>()
const showDialog = defineModel("showDialog", { type: Boolean, required: true })
const emit = defineEmits(["addResource", "editResource"])
const getEditorCompletions = useStudioCompletions(true)
const getCompletions = useStudioCompletions()

const emptyResource: Resource = {
	resource_id: "",
	resource_name: "",
	resource_type: "Document List",
	url: "",
	method: "GET",
	params: [],
	document_type: "",
	document_name: "",
	fetch_document_using_filters: false,
	fields: [],
	filters: {},
	limit: null,
	sort_field: "",
	sort_order: "",
	whitelisted_methods: [],
	transform: "",
	on_success: "",
	on_error: "",
}

const newResource = ref<Resource>({ ...emptyResource })
watch(
	() => props.resource,
	async () => {
		if (props.resource?.resource_id) {
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
		await doctypeFields.fetch()
		await whitelistedMethods.fetch()
		await sortFields.fetch()
	}

	return {
		...props.resource,
		source: "",
		resource_id: props.resource?.resource_id,
		resource_name: props.resource?.resource_name,
		filters: filters,
		fields: JSON.parse(props.resource?.fields || "[]"),
		params: getParamsArray(props.resource?.params),
		limit: props.resource?.limit || null,
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

const filterFields = ref<DocTypeField[]>([])

const doctypeFields = createResource({
	url: "studio.api.get_doctype_fields",
	makeParams,
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

const whitelistedMethods = createResource({
	url: "studio.api.get_whitelisted_methods",
	makeParams,
	transform: (data: string[]) => {
		return data.map((method) => {
			return {
				label: method,
				value: method,
			}
		})
	},
})

const sortFields = createResource({
	url: "studio.api.get_sort_fields",
	cache: ["sortFields", newResource.value.document_type],
	makeParams,
})

function makeParams() {
	return {
		doctype: props.resource?.document_type || newResource.value.document_type,
	}
}

function getTransformFnBoilerplate(resource_type: ResourceType) {
	if (resource_type == "Document") {
		return "function transform(doc) { \n\treturn doc; \n}"
	} else {
		return "function transform(data) { \n\treturn data; \n}"
	}
}

function getFnBoilerplate(event: "success" | "error") {
	if (event === "success") {
		return "function onSuccess(data) {}"
	} else {
		return "function onError(error) {}"
	}
}

watch(
	() => newResource.value?.document_type,
	(doctype) => {
		if (!doctype) return
		doctypeFields.fetch()
		whitelistedMethods.fetch()
		sortFields.fetch()
	},
)

watch(
	() => newResource.value?.resource_type,
	(resource_type) => {
		if (!resource_type || newResource.value.transform) return
		if (typeof resource_type === "string") {
			newResource.value.transform = getTransformFnBoilerplate(resource_type as ResourceType)
		}
	},
)

const requiredFields = computed(() => {
	const reqd: Record<string, string> = { resource_name: "Data Source Name" }
	if (newResource.value.resource_type === "API Resource") {
		reqd["url"] = "URL"
		reqd["method"] = "Method"
	} else {
		reqd["document_type"] = "Document Type"
		if (newResource.value.resource_type === "Document List") {
			reqd["fields"] = "Fields"
		} else {
			if (newResource.value.fetch_document_using_filters) {
				reqd["filters"] = "Filters"
			} else {
				reqd["document_name"] = "Document Name"
			}
		}
	}
	return reqd
})

const errorMessage = ref("")
const areRequiredFieldsFilled = () => {
	const missingFields = Object.keys(requiredFields.value).filter((field) => !newResource.value[field])
	if (missingFields.length) {
		errorMessage.value = `Please set ${missingFields.map((field) => requiredFields.value[field]).join(", ")}`
		return false
	} else {
		errorMessage.value = ""
		return true
	}
}

const reset = () => {
	newResource.value = { ...emptyResource }
	errorMessage.value = ""
}
</script>
