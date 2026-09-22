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
import { reactive, ref } from "vue";
import type { DocField } from "./types";
import { Button, Checkbox, Dialog, FormControl } from "frappe-ui";
import {
	downloadTemplate,
	fetchDoctypeBundle,
	fieldsToIgnore,
	getChildTableName,
} from "./dataImport";

const show = defineModel<boolean>({ required: true, default: false });
const fileType = ref<"Excel" | "CSV">("CSV");
const exportType = ref<"All Records" | "5 Records" | "Blank Template">("Blank Template");
const fieldSelection = ref<Record<string, Record<string, boolean>>>({});
const doctypeMeta = ref<any>(null);

const props = defineProps<{
	doctype: string;
}>();

const fields = reactive<{
	data: Record<string, { fieldname: string; label: string; reqd: number }[]>;
}>({
	data: {},
});
fetchDoctypeBundle(props.doctype).then((docs) => {
	doctypeMeta.value = docs;
	fields.data = transformFields({ docs });
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

const handleExport = async () => {
	await downloadTemplate({
		doctype: props.doctype,
		exportFields: getExportFields(),
		exportRecords: getExportType(),
		fileType: fileType.value,
	});
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
