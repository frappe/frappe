<template>
	<Dialog
		v-model:open="showDialog"
		:title="resource?.resource_id ? 'Edit Data Source' : 'Add Data Source'"
		size="2xl"
		@after-leave="reset"
	>
		<template #default>
			<div class="flex flex-col gap-4">
				<FormControl
					label="Data Source Name"
					:required="true"
					v-model="newResource.resource_name"
					autocomplete="off"
				/>
				<div class="flex w-full flex-row gap-2">
					<FormControl
						label="Type"
						type="select"
						:options="['Document List', 'Document', 'API Resource']"
						autocomplete="off"
						v-model="newResource.resource_type"
						class="w-full"
					/>
					<Link
						v-if="newResource.resource_type !== 'API Resource'"
						label="Document Type"
						:required="true"
						doctype="DocType"
						v-model="newResource.document_type"
						class="w-full"
					/>
					<FormControl
						v-else
						label="Method"
						type="select"
						:options="['GET', 'POST', 'PUT', 'DELETE']"
						v-model="newResource.method"
						class="w-full"
					/>
				</div>

				<!-- API Resource -->
				<template v-if="newResource.resource_type === 'API Resource'">
					<FormControl label="URL" v-model="newResource.url" :required="true" class="grow" />
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

				<!-- Document List -->
				<template v-if="newResource.resource_type === 'Document List' && newResource.document_type">
					<div class="flex flex-col gap-1.5">
						<FormControl
							label="Fields"
							:required="true"
							type="multiselect"
							:placeholder="`Select fields from ${newResource.document_type}`"
							v-model="newResource.fields"
							:options="fieldOptions"
						>
							<template #summary="{ selectedOptions, summary }">
								<template v-if="selectedOptions.length">
									{{
										selectedOptions
											.filter((o: SelectOption) => !invalidFields.has(o.value))
											.map((o: SelectOption) => o.label)
											.join(", ")
									}}
								</template>
								<template v-else>{{ summary }}</template>
							</template>
							<template #item-label="{ item }">
								<span :class="['truncate', invalidFields.has(item.value) && 'text-ink-gray-4 line-through']">
									{{ item.label }}
								</span>
							</template>
							<template #item-suffix="{ item }">
								<Badge v-if="invalidFields.has(item.value)" theme="amber" size="sm" variant="ghost">
									Missing Field
								</Badge>
							</template>
						</FormControl>
						<div v-if="invalidFields.size" class="flex items-center gap-1.5 text-p-sm text-ink-amber-7">
							<span class="lucide-triangle-alert size-3.5 shrink-0" />
							<span class="text-p-sm">
								<span class="font-medium">{{ [...invalidFields].join(", ") }}</span>
								{{ invalidFields.size === 1 ? "is no longer a field" : "are no longer fields" }} on
								{{ newResource.document_type }}.
								<button type="button" class="ml-1 underline" @click="removeInvalidFields">Remove</button>
							</span>
						</div>
					</div>
					<Filters label="Filters" v-model="newResource.filters" :docfields="filterFields" />
					<div class="flex w-full flex-row gap-2">
						<FormControl
							label="Sort Field"
							type="combobox"
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
						<FormControl
							label="Limit"
							type="number"
							placeholder="Number of records to fetch"
							v-model="newResource.limit"
							class="w-full"
							description="default: 20"
						/>
					</div>
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

					<Checkbox
						size="sm"
						v-model="newResource.fetch_document_using_filters"
						label="Dynamically fetch document using filters"
					/>

					<Filters
						v-if="newResource.fetch_document_using_filters"
						v-model="newResource.filters"
						:docfields="filterFields"
					/>

					<FormControl
						label="Whitelisted Methods"
						type="multiselect"
						v-model="newResource.whitelisted_methods"
						:options="whitelistedMethods.data"
					/>
				</template>

				<Checkbox size="sm" label="Auto fetch data on load" v-model="newResource.auto" />

				<!-- Transform Results for any Resource Type -->
				<ScriptSection
					title="Transform Results"
					description="Transform fetched data before use - reshape objects, format values or add extra properties"
					v-model="newResource.transform"
					:boilerplate="getTransformFnBoilerplate(newResource.resource_type)"
					:completions="getCompletions"
				/>

				<ScriptSection
					title="On Success"
					description="Update variables or control other data sources everytime the data loads successfully"
					v-model="newResource.on_success"
					:boilerplate="getFnBoilerplate('success')"
					:completions="(context: CompletionContext) => getEditorCompletions(context)"
				/>

				<ScriptSection
					title="On Failure"
					description="Handle errors gracefully with fallback logic or user alerts"
					v-model="newResource.on_error"
					:boilerplate="getFnBoilerplate('error')"
					:completions="(context: CompletionContext) => getEditorCompletions(context)"
				/>
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
import { createResource, Dialog, FormControl, Checkbox, ErrorMessage, Button, Badge } from "frappe-ui"
import Link from "@framework/ui/components/Link/Link.vue"
import ScriptSection from "@/components/ScriptSection.vue"
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
	transform: null,
	on_success: "",
	on_error: "",
	auto: true,
}

const newResource = ref<Resource>({ ...emptyResource })

// doctype metadata
const filterFields = ref<DocTypeField[]>([])

const doctypeFields = createResource({
	url: "studio.api.get_doctype_fields",
	makeParams: () => ({ ...makeParams(), with_standard_fields: true }),
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

watch(
	() => newResource.value?.document_type,
	(doctype) => {
		if (!doctype || doctype === doctypeFields.params?.doctype) return
		doctypeFields.fetch()
		whitelistedMethods.fetch()
		sortFields.fetch()
	},
)

function makeParams() {
	return {
		doctype: newResource.value.document_type || props.resource?.document_type,
	}
}

// selected fields that no longer exist on the doctype, kept as options so they can still be removed
const invalidFields = computed(() => {
	const available = new Set((doctypeFields.data || []).map((option: SelectOption) => option.value))
	return new Set((newResource.value.fields || []).filter((fieldname: string) => !available.has(fieldname)))
})

const fieldOptions = computed<SelectOption[]>(() => [
	...(doctypeFields.data || []),
	...[...invalidFields.value].map((fieldname) => ({ label: fieldname, value: fieldname })),
])

function removeInvalidFields() {
	newResource.value.fields = newResource.value.fields?.filter(
		(fieldname: string) => !invalidFields.value.has(fieldname),
	)
}

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

// script boilerplates
watch(
	() => newResource.value?.resource_type,
	(resource_type, oldResourceType) => {
		if (!resource_type) return
		const currentValue = newResource.value.transform
		if (currentValue == null || currentValue == undefined) return

		const oldBoilerplate = oldResourceType ? getTransformFnBoilerplate(oldResourceType as ResourceType) : null
		if (!currentValue || currentValue === oldBoilerplate) {
			newResource.value.transform = getTransformFnBoilerplate(resource_type as ResourceType)
		}
	},
)

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

// validation
const errorMessage = ref("")

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

function areRequiredFieldsFilled() {
	const missingFields = Object.keys(requiredFields.value).filter((field) => isEmpty(newResource.value[field]))
	if (missingFields.length) {
		errorMessage.value = `Please set ${missingFields.map((field) => requiredFields.value[field]).join(", ")}`
		return false
	} else {
		errorMessage.value = ""
		return true
	}
}

// fields and filters are an empty [] / {} when nothing is set
function isEmpty(value: unknown) {
	return typeof value === "object" ? isObjectEmpty(value) : !value
}

function reset() {
	newResource.value = { ...emptyResource }
	errorMessage.value = ""
}
</script>
