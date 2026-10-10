<template>
	<Dialog v-model:open="open" :title="t('Export Data')" size="2xl">
		<div class="flex flex-col gap-4">
			<div class="grid grid-cols-2 gap-4">
				<Select v-model="fileType" :label="t('File Type')" :options="fileTypeOptions" />
				<Select
					v-model="exportRecords"
					:label="t('Export Type')"
					:options="exportRecordOptions"
					:description="countMessage"
				/>
			</div>
			<div v-if="exportRecords === 'by_filter'">
				<Filter v-model="filters" :doctype="doctype" align="start" />
			</div>

			<div class="flex flex-col gap-4 border-t border-outline-gray-2 pt-4">
				<TextInput v-model="search" size="sm" :placeholder="t('Search')" />
				<div class="flex flex-col gap-2">
					<div class="text-sm-medium uppercase text-ink-gray-5">
						{{
							forInsert ? t("Select Fields To Insert") : t("Select Fields To Update")
						}}
					</div>
					<div class="flex gap-2">
						<Button size="xs" :label="t('Select All')" @click="selectAll" />
						<Button
							v-if="forInsert"
							size="xs"
							:label="t('Select Mandatory')"
							@click="selectMandatory"
						/>
						<Button size="xs" :label="t('Unselect All')" @click="unselectAll" />
					</div>
				</div>
				<div
					v-for="group in groups"
					:key="group.fieldname"
					class="flex flex-col gap-2"
					:data-group="group.fieldname"
				>
					<div class="text-base-medium text-ink-gray-8">{{ group.label }}</div>
					<div class="grid grid-cols-2 gap-x-4 gap-y-2">
						<Checkbox
							v-for="option in visibleOptions(group)"
							:key="option.value"
							:title="option.description"
							:data-option="option.value"
							:modelValue="!!selected[group.fieldname]?.[option.value]"
							@update:modelValue="
								(value) => setSelected(group.fieldname, option.value, !!value)
							"
						>
							<template #label>
								<span class="inline-flex items-center gap-1">
									{{ option.label }}
									<span v-if="option.danger" class="text-ink-red-6">*</span>
									<Tooltip v-if="option.warning" :text="option.warningTitle">
										<span class="lucide-info size-3 text-ink-gray-5" />
									</Tooltip>
								</span>
							</template>
						</Checkbox>
					</div>
				</div>
			</div>
		</div>
		<template #actions>
			<div class="flex justify-end">
				<Button
					variant="solid"
					:label="exportLabel"
					:disabled="!selectedFields(doctype).length"
					@click="exportRecordsNow"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Button, Checkbox, Dialog, Select, TextInput, Tooltip, call } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { Filter, serializeFilters } from "../../Filter";
import type { FilterCondition } from "../../Filter";
import { pickerColumns, postDownload, tableFields, type PickerField } from "../dataImport";
import { t } from "../translate";
import type { DataImportType, DocType, ImportProviderSchema } from "../types";

const DOWNLOAD_TEMPLATE_URL =
	"/api/method/frappe.core.doctype.data_import.data_import.download_template";

type ExportRecords = "all" | "by_filter" | "5_records" | "blank_template";

interface Group {
	fieldname: string;
	label: string;
	doctype: string | null;
}

interface Option {
	label: string;
	value: string;
	danger: boolean;
	warning: boolean;
	warningTitle: string;
	inImportTemplate: boolean;
	description: string;
}

const props = defineProps<{
	doctype: string;
	importType: DataImportType;
	providerSchema: ImportProviderSchema | null;
	doctypeMeta: DocType[] | null;
}>();

const open = defineModel<boolean>("open", { default: false });

const forInsert = computed(() => props.importType === "Insert New Records");

const fileType = ref<"Excel" | "CSV">("CSV");
const exportRecords = ref<ExportRecords>("blank_template");
const filters = ref<FilterCondition[]>([]);
const search = ref("");
const selected = ref<Record<string, Record<string, boolean>>>({});
const recordCount = ref<number | null>(null);

const fileTypeOptions = ["Excel", "CSV"];
const exportRecordOptions = computed(() => [
	{ label: t("All Records"), value: "all" },
	{ label: t("Filtered Records"), value: "by_filter" },
	{ label: t("5 Records"), value: "5_records" },
	{ label: t("Blank Template"), value: "blank_template" },
]);

const getMeta = (doctype: string | null) =>
	props.doctypeMeta?.find((meta) => meta.name === doctype) ?? null;

const fieldSource = computed(() => {
	const groups: Group[] = [];
	const columns: Record<string, PickerField[]> = {};
	const schema = props.providerSchema;
	if (schema) {
		const parentFields = schema.fields || [];
		groups.push({
			fieldname: props.doctype,
			label: t(props.doctype),
			doctype: parentFields[0]?.parent || props.doctype,
		});
		columns[props.doctype] = parentFields as PickerField[];
		for (const table of schema.child_tables || []) {
			const childFields = table.fields || [];
			groups.push({
				fieldname: table.fieldname,
				label: t(table.label || table.fieldname),
				doctype: childFields[0]?.parent || null,
			});
			columns[table.fieldname] = childFields as PickerField[];
		}
	} else if (getMeta(props.doctype)) {
		groups.push({ fieldname: props.doctype, label: t(props.doctype), doctype: props.doctype });
		columns[props.doctype] = pickerColumns(getMeta(props.doctype));
		for (const df of tableFields(getMeta(props.doctype))) {
			const childDoctype = df.options!;
			const args = [t(df.label || df.fieldname), t(childDoctype)];
			const label = df.reqd ? t("{0} ({1}) (1 row mandatory)", args) : t("{0} ({1})", args);
			groups.push({ fieldname: df.fieldname, label, doctype: childDoctype });
			columns[df.fieldname] = pickerColumns(getMeta(childDoctype));
		}
	}
	return { groups, columns };
});

const groups = computed(() => fieldSource.value.groups);

const optionsByGroup = computed(() =>
	Object.fromEntries(groups.value.map((group) => [group.fieldname, groupOptions(group)]))
);

function groupOptions(group: Group): Option[] {
	const fields = fieldSource.value.columns[group.fieldname] || [];
	const meta = getMeta(group.doctype);
	const autonameField = meta?.autoname?.startsWith("field:")
		? meta.fields.find((df) => df.fieldname === meta.autoname!.slice("field:".length))
		: undefined;
	const hideNameForAutoname =
		!!meta && forInsert.value && !["Prompt", "prompt"].includes(meta.autoname ?? "");
	const isAutonameField = (df: PickerField) =>
		!!autonameField && df.fieldname === autonameField.fieldname;

	const warningTitle = (df: PickerField) => {
		if (df.depends_on) return t("Depends on: {0}", [df.depends_on]);
		if (isAutonameField(df)) return t("Autoname: {0}", [autonameField!.label]);
		return "";
	};

	return fields
		.filter(
			(df) =>
				!(
					forInsert.value &&
					(autonameField || hideNameForAutoname) &&
					df.fieldname === "name"
				)
		)
		.map((df) => ({
			label: t(df.label || df.fieldname),
			value: df.fieldname,
			danger:
				(!!df.reqd && forInsert.value) || isAutonameField(df) || df.fieldname === "name",
			warning: (!!df.depends_on && forInsert.value) || isAutonameField(df),
			warningTitle: warningTitle(df) || t("Condition based field"),
			inImportTemplate: !!df.in_import_template,
			description: `${df.fieldname} ${df.reqd ? t("(Mandatory)") : ""}`,
		}));
}

function visibleOptions(group: Group) {
	const query = search.value.trim().toLowerCase();
	const options = optionsByGroup.value[group.fieldname] || [];
	return query
		? options.filter((option) => option.label.toLowerCase().includes(query))
		: options;
}

function setSelected(group: string, fieldname: string, value: boolean) {
	selected.value[group] = { ...selected.value[group], [fieldname]: value };
}

function setAll(pick: (group: Group, option: Option) => boolean) {
	selected.value = Object.fromEntries(
		groups.value.map((group) => [
			group.fieldname,
			Object.fromEntries(
				(optionsByGroup.value[group.fieldname] || []).map((option) => [
					option.value,
					pick(group, option),
				])
			),
		])
	);
}

const selectAll = () => setAll(() => true);
// Update imports match rows by ID, so Unselect All leaves its checkbox alone.
const unselectAll = () =>
	setAll(
		(group, option) =>
			!forInsert.value &&
			option.value === "name" &&
			!!selected.value[group.fieldname]?.[option.value]
	);

function selectMandatory() {
	// an optional table can opt in, like a Contact's links, emails and phones
	const mandatoryGroups = props.providerSchema
		? groups.value.map((group) => group.fieldname)
		: tableFields(getMeta(props.doctype))
				.filter((df) => df.reqd || df.in_import_template)
				.map((df) => df.fieldname)
				.concat(props.doctype);
	setAll(
		(group, option) =>
			mandatoryGroups.includes(group.fieldname) && (option.danger || option.inImportTemplate)
	);
}

function selectedFields(group: string) {
	return Object.keys(selected.value[group] || {}).filter(
		(field) => selected.value[group][field]
	);
}

const wireFilters = () => serializeFilters(filters.value);

let countRequest = 0;
async function updateRecordCount() {
	const request = ++countRequest;
	let count: number;
	if (exportRecords.value === "blank_template") count = 0;
	else if (exportRecords.value === "5_records") count = 5;
	else
		count = await call<number>("frappe.client.get_count", {
			doctype: props.doctype,
			filters: exportRecords.value === "by_filter" ? wireFilters() : undefined,
		}).catch(() => 0);
	if (request === countRequest) recordCount.value = Number(count) || 0;
}

const countMessage = computed(() => {
	if (recordCount.value === null) return "";
	if (recordCount.value === 0) return t("No records will be exported");
	if (recordCount.value === 1) return t("1 record will be exported");
	return t("{0} records will be exported", [recordCount.value]);
});

const exportLabel = computed(() => {
	if (!recordCount.value) return t("Export");
	if (recordCount.value === 1) return t("Export 1 record");
	return t("Export {0} records", [recordCount.value]);
});

function exportRecordsNow() {
	const exportFields = Object.fromEntries(
		groups.value.map((group) => [group.fieldname, selectedFields(group.fieldname)])
	);
	postDownload(DOWNLOAD_TEMPLATE_URL, {
		doctype: props.doctype,
		file_type: fileType.value,
		export_records: exportRecords.value,
		export_fields: exportFields,
		export_filters: exportRecords.value === "by_filter" ? wireFilters() : null,
	});
}

watch(
	open,
	(isOpen) => {
		if (!isOpen) return;
		search.value = "";
		filters.value = [];
		fileType.value = "CSV";
		exportRecords.value = forInsert.value ? "blank_template" : "all";
		updateRecordCount();
	},
	{ immediate: true }
);
watch([exportRecords, filters], () => open.value && updateRecordCount(), { deep: true });

// The field list can arrive after the dialog opens.
watch(
	[open, groups],
	([isOpen, current]) => {
		if (isOpen && current.length) selectMandatory();
	},
	{ immediate: true }
);
</script>
