<template>
	<Dialog
		v-model="show"
		:options="{
			title: 'Export Data',
			size: '2xl',
		}"
	>
		<template #body-content>
			<div class="text-base space-y-5">
				<div class="grid grid-cols-2 gap-5">
					<FormControl
						label="File Type"
						v-model="fileType"
						:options="['Excel', 'CSV']"
						type="select"
					/>
				</div>
				<div class="border-t">
					<p class="mt-2 text-ink-gray-5">
						Select the fields you want to include in the template.
					</p>
					<div class="space-x-2 mt-2 mb-5">
						<Button label="Select All" @click="selectAllFields" />
						<Button label="Select Mandatory Fields" @click="selectMandatoryFields" />
						<Button label="Unselect All" @click="unselectAllFields" />
					</div>
					<div class="space-y-8">
						<div
							v-for="doctype in Object.keys(fields.data)"
							:key="doctype"
							class="flex flex-col space-y-2"
						>
							<div class="text-ink-gray-5">
								{{ doctype }}
							</div>
							<div class="grid grid-cols-2 gap-5">
								<div
									v-for="field in fields.data[doctype]"
									:key="field.fieldname"
									class="flex items-center space-x-2"
								>
									<Checkbox
										:id="`checkbox-${doctype}-${field.fieldname}`"
										:checked="fieldSelection[doctype][field.fieldname]"
										@change="
											(e: Event) =>
												(fieldSelection[doctype][field.fieldname] = (
													e.target as HTMLInputElement
												).checked)
										"
									/>
									<label
										:for="`checkbox-${doctype}-${field.fieldname}`"
										:class="{
											'text-ink-red-6': field.reqd,
										}"
									>
										{{ field.label || field.fieldname }}
									</label>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>
		<template #actions="{ close }">
			<div class="flex justify-end space-x-2">
				<Button label="Export" variant="solid" @click="handleExport" />
				<Button label="Cancel" @click="close" />
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { ref } from "vue";
import type { DocField } from "./types";
import { Button, Checkbox, Dialog, FormControl, createResource } from "frappe-ui";
import { fieldsToIgnore, getChildTableName } from "./dataImport";

const show = defineModel<boolean>({ required: true, default: false });
const fileType = ref<"Excel" | "CSV">("CSV");
const exportType = ref<"All Records" | "5 Records" | "Blank Template">("Blank Template");
const fieldSelection = ref<Record<string, Record<string, boolean>>>({});
const doctypeMeta = ref<any>(null);

const props = defineProps<{
	doctype: string;
}>();

const fields = createResource({
	url: "frappe.desk.form.load.getdoctype",
	params: {
		doctype: props.doctype,
		with_parent: 1,
	},
	auto: true,
	transform(data: any) {
		doctypeMeta.value = data.docs;
		return transformFields(data);
	},
});

const transformFields = (data: any) => {
	let doctypeMap: Record<string, { fieldname: string; label: string; reqd: number }[]> = {};

	prepareDoctypeMap(data.docs, doctypeMap);
	addIDField(doctypeMap);
	updateFieldSelection(doctypeMap);

	return doctypeMap;
};

const prepareDoctypeMap = (
	docs: any[],
	doctypeMap: Record<string, { fieldname: string; label: string; reqd: number }[]>
) => {
	docs.forEach((doc: any) => {
		doctypeMap[doc.name] = doc.fields
			.filter((field: DocField) => {
				return !fieldsToIgnore.includes(field.fieldtype);
			})
			.map((field: DocField) => {
				return {
					fieldname: field.fieldname,
					label: field.label,
					reqd: field.reqd,
					disabled: doc.name == props.doctype && field.reqd ? true : false,
				};
			});
	});
};

const addIDField = (
	doctypeMap: Record<string, { fieldname: string; label: string; reqd: number }[]>
) => {
	Object.keys(doctypeMap).forEach((doctype: string) => {
		doctypeMap[doctype].unshift({
			fieldname: "name",
			label: "ID",
			reqd: 1,
		} as { fieldname: string; label: string; reqd: number });
	});
};

const updateFieldSelection = (
	doctypeMap: Record<string, { fieldname: string; label: string; reqd: number }[]>
) => {
	Object.keys(doctypeMap).forEach((doctype: string) => {
		if (!fieldSelection.value[doctype]) {
			fieldSelection.value[doctype] = {};
			if (doctype == props.doctype) {
				doctypeMap[doctype].forEach((field) => {
					if (field.reqd) {
						fieldSelection.value[doctype][field.fieldname] = true;
					}
				});
			}
		}
	});
};

const getExportURL = () => {
	let doctype = props.doctype;
	let exportFields = getExportFields();
	let exportRecords = getExportType();
	let exportPageLength = exportType.value == "5 Records" ? 5 : "";

	return `/api/method/frappe.core.doctype.data_import.data_import.download_template
        ?doctype=${encodeURIComponent(doctype)}
        &export_fields=${encodeURIComponent(JSON.stringify(exportFields))}
        &export_records=${encodeURIComponent(exportRecords)}
        &file_type=${encodeURIComponent(fileType.value)}
        &export_page_length=${exportPageLength}`.replace(/\s+/g, "");
};

const handleExport = async () => {
	let url = getExportURL();
	const response = await fetch(url);
	const blob = await response.blob();
	const link = document.createElement("a");

	link.href = URL.createObjectURL(blob);
	link.download = props.doctype + (fileType.value === "CSV" ? ".csv" : ".xlsx");
	document.body.appendChild(link);

	link.click();
	document.body.removeChild(link);
};

const getExportFields = () => {
	let exportFields: Record<string, string[]> = {};
	Object.keys(fieldSelection.value).forEach((doctype: string) => {
		let doctypeName =
			doctype == props.doctype
				? doctype
				: getChildTableName(doctype, props.doctype, doctypeMeta.value);
		exportFields[doctypeName] = Object.keys(fieldSelection.value[doctype]).filter(
			(fieldname: string) => fieldSelection.value[doctype][fieldname]
		);
	});
	return exportFields;
};

const getExportType = () => {
	if (exportType.value == "Blank Template") return "blank_template";
	if (exportType.value == "5 Records") return "5_records";
	return "all";
};

const selectAllFields = () => {
	Object.keys(fields.data).forEach((doctype: string) => {
		fields.data[doctype].forEach((field: DocField) => {
			if (!fieldSelection.value[doctype]) {
				fieldSelection.value[doctype] = {};
			}
			fieldSelection.value[doctype][field.fieldname] = true;
		});
	});
};

const selectMandatoryFields = () => {
	Object.keys(fields.data).forEach((doctype: string) => {
		fields.data[doctype].forEach((field: DocField) => {
			fieldSelection.value[doctype][field.fieldname] = field.reqd ? true : false;
		});
	});
};

const unselectAllFields = () => {
	Object.keys(fields.data).forEach((doctype: string) => {
		fields.data[doctype].forEach((field: DocField) => {
			fieldSelection.value[doctype][field.fieldname] = false;
		});
	});
};
</script>
