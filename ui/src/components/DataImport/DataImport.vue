<template>
	<header
		class="sticky flex items-center justify-between space-x-28 top-0 z-10 border-b bg-surface-base px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<ImportSteps
			class="flex-1 hidden lg:flex"
			v-if="step != 'list'"
			:data="data"
			:step="step"
			@updateStep="updateStep"
		/>
	</header>
	<div>
		<ImportSteps
			class="flex-1 lg:hidden w-[90%] mx-auto mt-5"
			v-if="step != 'list'"
			:data="data"
			:step="step"
			@updateStep="updateStep"
		/>

		<DataImportList
			v-if="step === 'list'"
			:dataImports="dataImports"
			@updateStep="updateStep"
		/>

		<UploadStep
			v-else-if="step === 'upload'"
			:dataImports="dataImports"
			:doctype="doctype || data?.reference_doctype"
			:fields="fields"
			:data="data"
			@updateStep="updateStep"
		/>

		<MappingStep
			v-else-if="step === 'map'"
			:dataImports="dataImports"
			:data="data as DataImport"
			:fields="fields"
			@updateStep="updateStep"
		/>

		<PreviewStep
			v-else-if="step === 'preview'"
			:dataImports="dataImports"
			:data="data as DataImport"
			:fields="fields"
			:doctypeMap="
				doctypeMap as Record<
					string,
					{ title: string; listRoute?: string; pageRoute?: string }
				>
			"
			:socket="socket"
			@updateStep="updateStep"
		/>
	</div>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import type { DataImportProps, DataImport } from "./types";
import { Breadcrumbs, createListResource, createResource } from "frappe-ui";
import { useRoute } from "vue-router";
import type { RouteLocationRaw } from "vue-router";
import DataImportList from "./DataImportList.vue";
import ImportSteps from "./ImportSteps.vue";
import MappingStep from "./MappingStep.vue";
import PreviewStep from "./PreviewStep.vue";
import UploadStep from "./UploadStep.vue";

const route = useRoute();
const step = ref<"upload" | "map" | "list" | "preview">("list");
const data = ref<DataImport | null>(null);

const props = defineProps<Partial<DataImportProps>>();

const dataImports = createListResource({
	doctype: "Data Import",
	fields: [
		"name",
		"reference_doctype",
		"import_type",
		"status",
		"creation",
		"mute_emails",
		"import_file",
		"google_sheets_url",
		"template_options",
	],
	auto: true,
	orderBy: "modified desc",
});

const fields = createResource({
	url: "frappe.desk.form.load.getdoctype",
	makeParams: (values: { doctype: string }) => {
		return {
			doctype: values.doctype,
			with_parent: 1,
		};
	},
	auto: false,
});

const updateData = () => {
	data.value = dataImports.data?.find((di: DataImport) => di.name === props.importName) || null;
};

watch(
	() => [route.params, props, dataImports.data],
	() => {
		if (props.doctype) {
			step.value = "upload";
			fields.reload({
				doctype: route.params.doctype,
			});
		} else if (props.importName) {
			updateData();
			if (!data.value?.import_file && !data.value?.google_sheets_url) {
				step.value = "upload";
			} else if (step.value == "upload" && route.query.step == "map") {
				step.value = route.query.step;
			} else {
				step.value = "preview";
			}
			if (data.value?.reference_doctype) {
				fields.reload({
					doctype: data.value?.reference_doctype,
				});
			}
		}
	},
	{ immediate: true }
);

watch(
	() => route.query,
	() => {
		if (route.query.step == "list") {
			step.value = "list";
		}
	}
);

const updateStep = (newStep: "list" | "upload" | "map" | "preview", newData: DataImport) => {
	step.value = newStep;
	if (newData) {
		data.value = newData;
	}
};

const doctypeTitle = computed(() => {
	let doctype = props.doctype || data.value?.reference_doctype;
	return props.doctypeMap?.[doctype || ""]?.title || doctype || "";
});

const breadcrumbs = computed(() => {
	let crumbs: { label: string; route?: RouteLocationRaw }[] = [
		{
			label: "Data Import",
			route: {
				name: "DataImportList",
				query: {
					step: "list",
				},
			},
		},
	];

	if (step.value !== "list") {
		crumbs.push({
			label: `Importing ${doctypeTitle.value}`,
		});
	}

	return crumbs;
});
</script>
