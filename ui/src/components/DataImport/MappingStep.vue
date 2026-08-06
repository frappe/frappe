<template>
	<div class="w-[85%] lg:w-[700px] mx-auto py-12 space-y-8 text-base">
		<div class="flex justify-between">
			<div class="space-y-2">
				<div class="text-md font-semibold text-ink-gray-9">
					<span> Map Data </span>
					<Badge v-if="data?.status" :theme="getBadgeColor(data?.status)">
						{{ data?.status }}
					</Badge>
				</div>
				<div class="leading-5 text-ink-gray-7">
					Change the mapping of columns from your file to fields in the system
				</div>
			</div>

			<div class="flex flex-col lg:flex-row space-y-2 lg:space-x-2 lg:space-y-0">
				<Button v-if="mappingUpdated" label="Reset Mapping" @click="resetMapping" />
				<Button label="Continue" variant="solid" @click="$emit('updateStep', 'preview')" />
			</div>
		</div>

		<div v-if="Object.keys(columnMappings).length" class="border rounded-md space-y-8">
			<div class="grid grid-cols-2 text-ink-gray-5 border-b py-2 px-4">
				<div>Fields in File</div>
				<div>Fields in System</div>
			</div>
			<div class="grid grid-cols-2 py-2 px-4 gap-y-8">
				<template v-for="i in columnsFromFile.length" :key="i">
					<div class="text-ink-gray-7">{{ columnsFromFile[i - 1] }}</div>
					<Combobox
						:model-value="columnMappings[columnsFromFile[i - 1]]"
						:options="columnsFromSystem"
						placeholder="Select field"
						@update:selected-option="
							(option: ComboboxOption | null) => updateColumnMappings(i, option)
						"
					/>
				</template>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import type { DataImport, DataImports } from "./types";
import { fieldsToIgnore, getBadgeColor, getPreviewData } from "./dataImport";
import { computed, nextTick, onMounted, ref } from "vue";
import { Badge, Button, Combobox, toast } from "frappe-ui";
import type { ComboboxOption } from "frappe-ui";

const previewData = ref<any>(null);
const emit = defineEmits(["updateStep"]);
const columnMappings = ref<Record<string, string>>({});
const mappingUpdated = ref(false);

const props = defineProps<{
	dataImports: DataImports;
	data: DataImport;
	fields: any;
}>();

onMounted(async () => {
	previewData.value = await getPreviewData(
		props.data.name!,
		props.data.import_file,
		props.data.google_sheets_url
	);
	initializeColumnMappings();
});

const initializeColumnMappings = () => {
	const mappings: Record<string, string> = {};
	let columnToFieldMap = [];
	if (props.data?.template_options)
		columnToFieldMap = JSON.parse(props.data?.template_options)?.["column_to_field_map"];

	if (Object.keys(columnToFieldMap).length > 0) mappingUpdated.value = true;

	columnsFromFile.value.forEach((col: string, index: number) => {
		// A mapped column holds the target fieldname; an unmapped one falls back
		// to the file's own header, which Combobox shows verbatim because no
		// option matches it.
		if (columnToFieldMap && columnToFieldMap[index]) mappings[col] = columnToFieldMap[index];
		else mappings[col] = col;
	});

	columnMappings.value = mappings;
};

const updateColumnMappings = (index: number, value: ComboboxOption | null) => {
	// Only a plain selectable option carries a `value`; custom rows and group
	// headers do not, and this combobox renders neither.
	if (!value || typeof value === "string" || !("value" in value)) return;
	mappingUpdated.value = true;
	let templateOptions = props.data?.template_options
		? JSON.parse(props.data?.template_options)
		: {};
	let columnToFieldMap = templateOptions["column_to_field_map"] || {};
	columnToFieldMap[index - 1] = value.value;

	props.dataImports.setValue.submit(
		{
			...props.data,
			template_options: JSON.stringify({
				...templateOptions,
				column_to_field_map: columnToFieldMap,
			}),
		},
		{
			onSuccess: (data: DataImport) => {
				emit("updateStep", "map", { ...data });
				nextTick(() => {
					initializeColumnMappings();
				});
			},
			onError: (error: any) => {
				toast.error(error.messages?.[0] || error);
				console.error("Error updating column mappings:", error);
			},
		}
	);
};

const columnsFromFile = computed(() => {
	const columns: string[] = [];
	previewData.value?.columns.forEach((col: any) => {
		if (col.header_title != "Sr. No") columns.push(col.header_title);
	});
	return columns;
});

const columnsFromSystem = computed(() => {
	const parent = props.data!.reference_doctype;
	const docs = props.fields.data?.docs || [];

	return docs
		.map((doc: any) => {
			const isParent = doc.name === parent;

			const columns = doc.fields
				.filter((f: any) => !fieldsToIgnore.includes(f.fieldtype))
				.map((f: any) => ({
					value: f.fieldname,
					label: isParent
						? f.label
						: `${f.label} (${getChildTableName(parent, doc.name)})`,
				}));

			return [{ value: "name", label: "ID" }, ...columns];
		})
		.flat();
});

const resetMapping = () => {
	let templateOptions = props.data?.template_options
		? JSON.parse(props.data?.template_options)
		: {};
	props.dataImports.setValue.submit(
		{
			...props.data,
			template_options: JSON.stringify({
				...templateOptions,
				column_to_field_map: {},
			}),
		},
		{
			onSuccess: (data: DataImport) => {
				emit("updateStep", "map", { ...data });
				nextTick(() => {
					initializeColumnMappings();
				});
			},
			onError: (error: any) => {
				toast.error(error.messages?.[0] || error);
				console.error("Error resetting column mappings:", error);
			},
		}
	);
};

const getChildTableName = (parent: string, child: string) => {
	let parentFields =
		props.fields.data?.docs.find((doc: any) => doc.name == parent)?.fields || [];

	let childField = parentFields.filter((field: any) => field.options == child)[0];
	return childField?.label || child;
};
</script>
