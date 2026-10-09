<template>
	<div class="flex w-full min-w-0 flex-col gap-3">
		<div class="flex items-center justify-between gap-2">
			<div v-if="!isSuccess" class="text-base text-ink-gray-6">
				{{ t("Map each file column to a field.") }}
			</div>
			<div
				data-testid="row-count"
				class="ms-auto whitespace-nowrap text-right text-base text-ink-gray-6"
			>
				{{ rowCountText }}
			</div>
		</div>

		<TooltipProvider>
			<div
				class="w-full min-w-0 overflow-x-auto rounded-5 border border-outline-gray-2 bg-surface-base"
			>
				<table
					class="table-fixed border-separate border-spacing-0 text-base text-ink-gray-8"
					:style="{ width: `${tableWidth}px` }"
				>
					<colgroup>
						<col
							v-for="(column, i) in columns"
							:key="i"
							:style="{ width: `${column.width}px` }"
						/>
					</colgroup>
					<thead>
						<tr class="h-[42px]">
							<th
								v-for="(column, i) in columns"
								:key="i"
								:class="[
									cellClass,
									'bg-surface-base text-left font-normal',
									i === 0 && stickyClass,
								]"
							>
								<span v-if="i === 0" class="text-ink-gray-5">{{ t("Sr") }}</span>
								<Combobox
									v-else
									class="w-full"
									size="sm"
									:model-value="column.mappedTo"
									:options="fieldOptions"
									:disabled="!canEdit"
									@update:model-value="(value) => remapColumn(i, value)"
								/>
							</th>
						</tr>
					</thead>
					<tbody>
						<tr class="h-[42px] font-medium">
							<td
								v-for="(column, i) in columns"
								:key="i"
								:class="[
									cellClass,
									column.greyed ? greyedClass : 'bg-surface-gray-1',
									i === 0 && stickyClass,
								]"
							>
								<span v-if="i === 0">1</span>
								<span v-else class="flex min-w-0 items-center gap-2">
									<span v-if="column.title" class="min-w-0 truncate">{{
										column.title
									}}</span>
									<i v-else class="min-w-0 truncate">{{
										t("Untitled Column")
									}}</i>
									<Dropdown
										v-if="column.isDate"
										align="end"
										:options="dateFormatMenu(column, i)"
									>
										<Button
											data-slot="date-format"
											class="ms-auto shrink-0"
											size="xs"
											variant="ghost"
											icon="lucide-ellipsis"
											:title="
												column.dateFormat
													? dateFormatLabel(column.dateFormat)
													: t('Select date format')
											"
											:disabled="!canEdit"
										/>
									</Dropdown>
								</span>
							</td>
						</tr>
						<tr
							v-for="(row, r) in rows"
							:key="r"
							:class="['h-[42px]', isImported(row) && 'pointer-events-none']"
							:data-highlighted="row[0] === highlightedRow || undefined"
							:data-imported="isImported(row) || undefined"
						>
							<td
								v-for="(column, i) in columns"
								:key="i"
								:class="[
									cellClass,
									'max-w-0',
									isImported(row)
										? 'bg-surface-gray-1 text-ink-gray-8'
										: row[0] === highlightedRow
										? 'bg-surface-amber-2'
										: column.greyed
										? greyedClass
										: 'bg-surface-base',
									i === 0 && stickyClass,
								]"
							>
								<Tooltip :text="cellText(row[i])" :disabled="!cellText(row[i])">
									<span class="block truncate">{{ cellText(row[i]) }}</span>
								</Tooltip>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</TooltipProvider>

		<div v-if="skippedColumns.length" class="flex flex-wrap items-center gap-1.5">
			<span class="text-sm text-ink-gray-6">{{ t("Not imported:") }}</span>
			<Badge
				v-for="column in skippedColumns"
				:key="column.index"
				:label="column.title || t('Untitled Column')"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, Combobox, Dropdown, Tooltip, TooltipProvider } from "frappe-ui";
import { computed } from "vue";
import { parseJson, pickerColumns, tableFields } from "../dataImport";
import { t } from "../translate";
import type { DocType, ImportProviderSchema } from "../types";
import type { UseDataImport } from "../useDataImport";

// The server checks for this exact value, so it is not translated.
const DONT_IMPORT = "Don't Import";
const DATE_FIELDTYPES = ["Date", "Datetime", "Time"];
const COMMON_DATE_FORMATS = [
	"%Y-%m-%d",
	"%d-%m-%Y",
	"%m-%d-%Y",
	"%d/%m/%Y",
	"%m/%d/%Y",
	"%Y/%m/%d",
	"%d.%m.%Y",
	"%d-%b-%Y",
];
const COMMON_TIME_FORMATS = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"];

const cellClass = "border-b border-r border-outline-gray-1 px-2 align-middle";
const stickyClass = "sticky left-0 z-[1]";
const greyedClass = "bg-surface-gray-2 text-ink-gray-4";

const props = defineProps<{ dataImport: UseDataImport; highlightedRow?: number | null }>();
const { doc, preview, saving, providerSchema, doctypeMeta } = props.dataImport;

const isSuccess = computed(() => doc.value.status === "Success");
const canEdit = computed(() => !isSuccess.value && !saving.value);

const templateOptions = computed(() =>
	parseJson<Record<string, any>>(doc.value.template_options, {})
);

const columns = computed(() =>
	(preview.value?.columns ?? []).map((column, i) => {
		const df = column.df;
		const title: string = column.header_title || "";
		if (i === 0) return { index: i, title, width: 56, greyed: false };
		const mappedTo = mappedField(column, i);
		const isDate = !column.skip_import && !!df && DATE_FIELDTYPES.includes(df.fieldtype);
		let width = Math.max(140, Math.min(260, (title || df?.label || "").length * 9 + 48));
		if (isDate) width = Math.max(width, 200);
		return {
			index: i,
			title: column.skip_import || !df ? title : title || df.label,
			width,
			mappedTo,
			greyed: mappedTo === DONT_IMPORT,
			isDate,
			fieldtype: df?.fieldtype as string | undefined,
			dateFormat: (templateOptions.value.column_to_date_format_map?.[i - 1] ??
				column.date_format) as string | null,
		};
	})
);

const tableWidth = computed(() => columns.value.reduce((sum, column) => sum + column.width, 0));
const skippedColumns = computed(() => columns.value.filter((column) => column.greyed));
const rows = computed(() => preview.value?.data ?? []);

const importedRows = computed(() => {
	const rowNumbers = new Set<number>();
	for (const log of preview.value?.import_log ?? []) {
		if (log.success)
			for (const n of parseJson<number[]>(log.row_indexes, [])) rowNumbers.add(n);
	}
	return rowNumbers;
});
const isImported = (row: unknown[]) => importedRows.value.has(row[0] as number);

const rowCountText = computed(() => {
	const data = preview.value;
	const visible = rows.value.length;
	if (!data || !visible) return "";
	const total = data.total_number_of_rows ?? visible;
	const shown = data.max_rows_exceeded ? data.max_rows_in_preview : visible;
	if (data.max_rows_exceeded || shown! < total)
		return t("Showing first {0} rows of {1}", [shown, total]);
	return total === 1 ? t("1 row") : t("Showing all {0} rows", [total]);
});

const fieldOptions = computed(() => [
	{ label: t("Don't Import"), value: DONT_IMPORT },
	...fieldsAsOptions(doc.value.reference_doctype, providerSchema.value, doctypeMeta.value),
]);

function mappedField(column: Record<string, any>, i: number): string {
	const picked = templateOptions.value.column_to_field_map?.[i - 1];
	if (picked) return picked;
	if (column.skip_import || !column.df) return DONT_IMPORT;
	if (column.map_to_field) return column.map_to_field;
	if (column.is_child_table_field)
		return `${column.child_table_df.fieldname}.${column.df.fieldname}`;
	return column.df.fieldname;
}

function cellText(value: unknown) {
	return value == null ? "" : String(value);
}

/** Both maps are keyed by the file's column index, which skips the row-number column. */
function setTemplateOption(key: string, columnIndex: number, value: string) {
	const options = parseJson<Record<string, any>>(doc.value.template_options, {});
	options[key] ||= {};
	if (options[key][columnIndex - 1] === value) return;
	options[key][columnIndex - 1] = value;
	doc.value.template_options = JSON.stringify(options);
	props.dataImport.save().catch(() => {});
}

function remapColumn(columnIndex: number, value: string | number | null | undefined) {
	if (!canEdit.value) return;
	setTemplateOption("column_to_field_map", columnIndex, String(value || DONT_IMPORT));
}

function dateFormatMenu(column: { fieldtype?: string; dateFormat: string | null }, i: number) {
	const current = column.dateFormat || "";
	const formats = dateFormatOptions(column.fieldtype);
	if (current && !formats.some((format) => format.value === current))
		formats.unshift({ value: current, label: dateFormatLabel(current), detected: true });
	return [
		{
			group: t("Select date format"),
			options: formats.map((format) => ({
				label: format.detected ? t("{0} (detected)", [format.label]) : format.label,
				selected: format.value === current,
				onClick: () => setTemplateOption("column_to_date_format_map", i, format.value),
			})),
		},
	];
}

/** "%Y-%m-%d" -> "yyyy-mm-dd" */
function dateFormatLabel(format: string) {
	return format
		.replace(/%Y/g, "yyyy")
		.replace(/%y/g, "yy")
		.replace(/%m/g, "mm")
		.replace(/%d/g, "dd")
		.replace(/%B/g, "Month")
		.replace(/%b/g, "Mon")
		.replace(/%H/g, "HH")
		.replace(/%I/g, "hh")
		.replace(/%M/g, "mm")
		.replace(/%S/g, "ss")
		.replace(/%p/g, "AM/PM")
		.replace(/%f/g, "SSS");
}

function dateFormatOptions(fieldtype?: string) {
	const values =
		fieldtype === "Time"
			? COMMON_TIME_FORMATS
			: fieldtype === "Datetime"
			? COMMON_DATE_FORMATS.map((format) => `${format} %H:%M:%S`)
			: COMMON_DATE_FORMATS;
	return values.map((value) => ({
		value,
		label: dateFormatLabel(value),
		detected: false,
	}));
}

type PickerField = { label: string; fieldname: string; parent?: string };

/** The parent's fields, then each child table's as `table.field`, each with an ID first. */
function fieldsAsOptions(
	doctype: string,
	schema: ImportProviderSchema | null,
	meta: DocType[] | null
) {
	const groups: { key: string; tableLabel?: string; fields: PickerField[] }[] = [];
	if (schema) {
		groups.push({ key: doctype, fields: schema.fields as PickerField[] });
		for (const table of schema.child_tables ?? [])
			groups.push({
				key: table.fieldname,
				tableLabel: table.label,
				fields: table.fields as PickerField[],
			});
	} else if (meta) {
		const parent = meta.find((d) => d.name === doctype);
		if (!parent) return [];
		groups.push({ key: doctype, fields: pickerColumns(parent) as PickerField[] });
		for (const table of tableFields(parent)) {
			const child = meta.find((d) => d.name === table.options);
			if (child)
				groups.push({
					key: table.fieldname,
					tableLabel: table.label,
					fields: pickerColumns(child) as PickerField[],
				});
		}
	}
	return groups.flatMap(({ key, tableLabel, fields }) =>
		fields.map((df) => {
			const isChild = key !== doctype;
			const value = isChild ? `${key}.${df.fieldname}` : df.fieldname;
			const label = isChild
				? `${t(df.label)} (${t(tableLabel || df.parent || key)})`
				: t(df.label);
			return { label, value, description: value };
		})
	);
}
</script>
