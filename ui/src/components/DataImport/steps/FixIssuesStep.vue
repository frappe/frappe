<template>
	<div
		v-if="checking"
		class="flex w-full flex-col gap-3"
		role="status"
		aria-busy="true"
		:aria-label="t('Checking import file for issues...')"
	>
		<Skeleton class="h-5 w-[55%] rounded" />
		<Skeleton class="h-3.5 w-full rounded" />
		<Skeleton class="h-3.5 w-[92%] rounded" />
		<Skeleton class="h-3.5 w-[88%] rounded" />
		<Skeleton class="h-[18px] w-[35%] rounded" />
		<Skeleton v-for="i in 3" :key="i" class="h-9 w-full rounded" />
	</div>

	<div
		v-else-if="!hasIssues"
		class="flex min-h-96 flex-col items-center justify-center gap-2 text-center"
	>
		<span class="lucide-list-checks size-6 text-ink-gray-5" />
		<div class="text-lg-semibold text-ink-gray-8">{{ t("No issues to fix") }}</div>
		<div class="text-base text-ink-gray-6">{{ emptyDescription }}</div>
		<div
			v-if="hasImportFile"
			class="flex w-full max-w-4xl pt-4"
			role="list"
			:aria-label="t('Fix issues summary')"
		>
			<div
				v-for="stat in stats"
				:key="stat.label"
				class="flex flex-1 flex-col items-center justify-center gap-1"
				role="listitem"
			>
				<div class="text-2xl-semibold text-ink-gray-8">{{ stat.value }}</div>
				<div class="text-center text-sm text-ink-gray-6">{{ stat.label }}</div>
			</div>
		</div>
	</div>

	<div v-else class="flex w-full flex-col divide-y divide-outline-gray-2 text-base">
		<section v-if="rowErrors.length" class="flex flex-col gap-3 py-4 first:pt-0 last:pb-0">
			<div class="text-base-semibold text-ink-gray-9">{{ t("Row errors") }}</div>
			<div data-slot="scroll" class="flex max-h-72 flex-col gap-3 overflow-y-auto">
				<div
					v-for="{ row, lines } in rowErrors"
					:key="row"
					class="flex flex-col gap-1"
					:data-row="row"
				>
					<div class="flex items-center justify-between gap-3">
						<HoverCard :hover-delay="250" :leave-delay="150">
							<template #trigger>
								<button
									type="button"
									class="text-base-semibold text-ink-gray-9 underline underline-offset-2"
								>
									{{ t("Row {0}", [row]) }}
								</button>
							</template>
							<div class="max-w-[min(90vw,56rem)] overflow-x-auto p-2">
								<table v-if="previewRow(row)" class="border-collapse text-sm">
									<thead>
										<tr>
											<th
												v-for="(label, i) in previewHeaders"
												:key="i"
												class="whitespace-nowrap border border-outline-gray-1 bg-surface-gray-2 px-2.5 py-1.5 text-left font-semibold text-ink-gray-9"
											>
												{{ label }}
											</th>
										</tr>
									</thead>
									<tbody>
										<tr>
											<td
												v-for="(_, i) in previewHeaders"
												:key="i"
												:title="cellText(previewRow(row)![i])"
												class="whitespace-nowrap border border-outline-gray-1 px-2.5 py-1.5 text-left"
											>
												{{ cellText(previewRow(row)![i]) }}
											</td>
										</tr>
									</tbody>
								</table>
								<div v-else class="text-sm text-ink-gray-6">
									{{ t("No preview data for this row") }}
								</div>
							</div>
						</HoverCard>
						<Button
							size="xs"
							variant="outline"
							class="shrink-0"
							:label="skippedRows.has(row) ? t('Undo Skip') : t('Skip Row')"
							:disabled="running"
							@click="toggleSkipRows([row])"
						/>
					</div>
					<ul
						class="flex flex-col gap-1 leading-normal text-ink-gray-8"
						:class="{ 'opacity-60': skippedRows.has(row) }"
					>
						<li v-for="(line, i) in lines" :key="i" v-html="line" />
					</ul>
				</div>
			</div>
		</section>

		<section v-if="showMappingSection" class="flex flex-col gap-3 py-4 first:pt-0 last:pb-0">
			<div class="text-base-semibold text-ink-gray-9">{{ t("Mapping warnings") }}</div>
			<div
				v-if="mappingColumnsHtml"
				class="leading-normal text-ink-gray-7"
				v-html="
					t(
						'Some columns have invalid values. Map them to valid values below, or skip the rows that have them. Affected columns: {0}.',
						[mappingColumnsHtml]
					)
				"
			/>
			<div
				v-if="doc.value_mappings.length"
				data-slot="scroll"
				class="max-h-96 overflow-auto rounded-5 border border-outline-gray-1"
			>
				<table class="w-full min-w-[44rem] table-fixed border-collapse text-base">
					<thead class="sticky top-0 z-[1] bg-surface-gray-2 text-left text-ink-gray-7">
						<tr>
							<th class="w-16 whitespace-nowrap px-3 py-2 font-medium">
								{{ t("No.") }}
							</th>
							<th class="w-40 whitespace-nowrap px-3 py-2 font-medium">
								{{ t("Column") }}
							</th>
							<th class="whitespace-nowrap px-3 py-2 font-medium">
								{{ t("Value in File") }}
							</th>
							<th class="w-28 whitespace-nowrap px-3 py-2 font-medium">
								{{ t("No. of Rows") }}
							</th>
							<th class="w-64 whitespace-nowrap px-3 py-2 font-medium">
								{{ t("Map To") }}
							</th>
							<th class="w-24 px-3 py-2 font-medium">
								<div class="flex items-center justify-center gap-2">
									<span>{{ t("Skip") }}</span>
									<Checkbox
										data-slot="skip-all"
										:aria-label="t('Skip all')"
										:modelValue="allValuesSkipped"
										:indeterminate="!allValuesSkipped && someValuesSkipped"
										:disabled="!skippableMappings.length"
										@update:modelValue="toggleSkipAll"
									/>
								</div>
							</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="(mapping, index) in doc.value_mappings"
							:key="mapping.name ?? index"
							class="border-t border-outline-gray-1"
							:class="
								isValueSkipped(mapping) ? 'text-ink-gray-5' : 'text-ink-gray-8'
							"
						>
							<td class="px-3 py-1.5 text-ink-gray-5">{{ index + 1 }}</td>
							<td class="truncate px-3 py-1.5" :title="mapping.column_label">
								{{ mapping.column_label }}
							</td>
							<td class="truncate px-3 py-1.5" :title="mapping.source_value">
								{{ mapping.source_value }}
							</td>
							<td class="px-3 py-1.5">{{ mapping.no_of_rows }}</td>
							<td class="px-3 py-1.5">
								<Link
									v-if="mapping.fieldtype === 'Link' && mapping.link_doctype"
									data-slot="map-to-link"
									class="w-full"
									:class="
										mapping.create_new &&
										'[&_input]:placeholder:text-ink-gray-8'
									"
									:modelValue="mapping.target_value"
									:doctype="mapping.link_doctype"
									:placeholder="
										mapping.create_new
											? t('Create {0}', [mapping.source_value])
											: undefined
									"
									:disabled="!canMap(mapping)"
									:creatable="!!mapping.can_create"
									@update:modelValue="(value) => mapTo(mapping, value)"
									@create="createOnImport(mapping)"
								>
									<template v-if="mapping.create_new" #prefix>
										<span
											class="lucide-plus size-4 shrink-0 text-ink-gray-7"
										/>
									</template>
									<template #item-create>
										<span class="truncate">
											{{ t("Create {0}", [mapping.source_value]) }}
										</span>
									</template>
								</Link>
								<Select
									v-else-if="
										mapping.fieldtype === 'Select' && mapping.select_options
									"
									class="w-full"
									v-model="mapping.target_value"
									:options="mapping.select_options.split('\n')"
									:disabled="!canMap(mapping)"
								/>
								<TextInput
									v-else
									class="w-full"
									:modelValue="mapping.target_value || ''"
									:disabled="!canMap(mapping)"
									@update:modelValue="
										(value) => (mapping.target_value = String(value))
									"
								/>
							</td>
							<td class="px-3 py-1.5">
								<div class="flex justify-center">
									<Checkbox
										data-slot="skip-value"
										:aria-label="t('Skip')"
										:modelValue="isValueSkipped(mapping)"
										:disabled="!canSkipValue(mapping)"
										@update:modelValue="toggleSkipRows(rowNumbers(mapping))"
									/>
								</div>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>

		<section
			v-if="columnWarnings.length || skippedColumns.length"
			class="flex flex-col gap-3 py-4 first:pt-0 last:pb-0"
		>
			<ul
				v-if="columnWarnings.length"
				data-slot="scroll"
				class="flex max-h-48 flex-col gap-2 overflow-y-auto"
			>
				<li
					v-for="warning in columnWarnings"
					:key="warning.col"
					class="flex items-baseline gap-3"
					:data-col="warning.col"
				>
					<span class="w-20 shrink-0 text-sm text-ink-gray-5">
						{{ t("Column {0}", [warning.col]) }}
					</span>
					<div class="min-w-0 text-ink-gray-8" v-html="warning.message" />
				</li>
			</ul>
			<HoverCard v-if="skippedColumns.length" :hover-delay="250" :leave-delay="150">
				<template #trigger>
					<button
						type="button"
						data-slot="skipped-columns"
						class="flex items-center gap-1.5 self-start text-sm text-ink-gray-6 hover:text-ink-gray-8"
					>
						<span class="lucide-columns-3 size-4 shrink-0" />
						<span class="underline decoration-dotted underline-offset-2">
							{{
								skippedColumns.length === 1
									? t("1 column skipped")
									: t("{0} columns skipped", [skippedColumns.length])
							}}
						</span>
					</button>
				</template>
				<div class="flex max-w-sm flex-wrap gap-1.5 p-2">
					<Badge
						v-for="column in skippedColumns"
						:key="column.col"
						:label="column.label"
						theme="gray"
					/>
				</div>
			</HoverCard>
		</section>

		<section v-if="otherWarnings.length" class="flex flex-col gap-3 py-4 first:pt-0 last:pb-0">
			<div class="text-base-semibold text-ink-gray-9">{{ t("Issues") }}</div>
			<div data-slot="scroll" class="flex max-h-48 flex-col gap-3 overflow-y-auto">
				<div
					v-for="(warning, index) in otherWarnings"
					:key="index"
					class="flex items-start justify-between gap-3"
				>
					<div
						class="leading-normal text-ink-gray-8"
						:class="{ 'opacity-60': duplicateSkipped(warning) }"
						v-html="warning.message"
					/>
					<Button
						v-if="isDuplicateId(warning)"
						size="xs"
						variant="outline"
						class="shrink-0"
						:label="
							duplicateSkipped(warning)
								? t('Undo Skip Duplicates')
								: t('Keep Row {0}, Skip Rest', [warning.rows[0]])
						"
						:disabled="running"
						@click="toggleSkipRows(warning.rows.slice(1))"
					/>
				</div>
			</div>
		</section>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, Checkbox, HoverCard, Select, Skeleton, TextInput } from "frappe-ui";
import { computed } from "vue";
import { Link } from "../../Link";
import { escapeHtml, isImportComplete, parseJson } from "../dataImport";
import { t } from "../translate";
import type { DataImportValueMapping } from "../types";
import type { UseDataImport } from "../useDataImport";

type Warning = Record<string, any>;

const props = defineProps<{ dataImport: UseDataImport }>();

const { doc, hasImportFile, preview, previewReady, previewError, running, importStarted } =
	props.dataImport;

const previewData = computed(() => (previewReady.value ? preview.value : null));
const checking = computed(() => hasImportFile.value && !previewReady.value && !previewError.value);
const isComplete = computed(() => isImportComplete(doc.value.status));

const warnings = computed(() => {
	const saved = parseJson<Warning[]>(doc.value.template_warnings, []);
	return dedupeWarnings(saved.concat(previewData.value?.warnings ?? []));
});

const hasIssues = computed(
	() =>
		!isComplete.value &&
		(warnings.value.length > 0 ||
			doc.value.value_mappings.length > 0 ||
			doc.value.skipped_rows.length > 0)
);

const skippedRows = computed(
	() => new Set(doc.value.skipped_rows.map((row) => Number(row.row_number)))
);

const columns = computed(() => previewData.value?.columns ?? []);

const rowErrors = computed(() => {
	const byRow = new Map<number, string[]>();
	for (const warning of warnings.value) {
		if (!warning.row) continue;
		const row = Number(warning.row);
		if (!byRow.has(row)) byRow.set(row, []);
		byRow.get(row)!.push(rowWarningLine(warning));
	}
	return [...byRow.entries()].sort(([a], [b]) => a - b).map(([row, lines]) => ({ row, lines }));
});

const mappingWarnings = computed(() =>
	warnings.value.filter((w) => !w.row && w.col && w.type === "value_mapping")
);
// Columns the server drops (duplicate, "Don't Import", untitled) need no action,
// so they collapse into one line; an unmatched header can still be mapped.
const isSkippedColumn = (w: Warning) =>
	!!columns.value[w.col]?.skip_import && w.code !== "unknown_column";
const allColumnWarnings = computed(() =>
	warnings.value.filter((w) => !w.row && w.col && w.type !== "value_mapping")
);
const columnWarnings = computed(() => allColumnWarnings.value.filter((w) => !isSkippedColumn(w)));
const skippedColumns = computed(() =>
	allColumnWarnings.value.filter(isSkippedColumn).map((w) => ({
		col: w.col,
		label: columns.value[w.col]?.header_title || t("Column {0}", [w.col]),
	}))
);
const otherWarnings = computed(() => warnings.value.filter((w) => !w.row && !w.col));

const showMappingSection = computed(
	() => mappingWarnings.value.length > 0 || doc.value.value_mappings.length > 0
);

const mappingColumnsHtml = computed(() => {
	const labels = new Set(
		mappingWarnings.value.map(
			(w) => columns.value[w.col]?.header_title || t("Column {0}", [w.col])
		)
	);
	return [...labels].map((label) => `<strong>${escapeHtml(label)}</strong>`).join(", ");
});

const previewHeaders = computed(() =>
	columns.value.map((col, i) => col.header_title || col.df?.label || t("Column {0}", [i]))
);

const emptyDescription = computed(() => {
	if (!hasImportFile.value) return t("Attach an import file to validate rows and mappings.");
	if (isComplete.value)
		return t("This import is complete. There are no pending warnings or mapping issues.");
	return t("No warnings or mapping issues were found. You can continue to import.");
});

const stats = computed(() => {
	const data = previewData.value;
	const rowsChecked =
		data?.total_number_of_rows || data?.data?.length || doc.value.payload_count || 0;
	const columnsMatched = columns.value.filter(
		(col) => !isSrNoColumn(col) && !col.skip_import && !!col.df
	).length;
	return [
		{ value: rowsChecked, label: t("Rows checked") },
		{ value: columnsMatched, label: t("Columns matched") },
		{ value: doc.value.skipped_rows.length, label: t("Rows skipped") },
	];
});

// The message is cleaned on the server; the field's label and parent are not.
function rowWarningLine(warning: Warning) {
	if (!warning.field) return warning.message;
	const { label, parent } = warning.field;
	const table = parent !== doc.value.reference_doctype ? ` (${escapeHtml(String(parent))})` : "";
	return `${escapeHtml(String(label ?? ""))}${table}: ${warning.message}`;
}

function previewRow(row: number) {
	const { data = [], warning_rows = [] } = previewData.value ?? {};
	return [...data, ...warning_rows].find((r) => Number(r[0]) === row);
}

function cellText(value: unknown) {
	return value == null || value === "" ? "—" : String(value);
}

function rowNumbers(mapping: DataImportValueMapping): number[] {
	return parseJson<unknown[]>(mapping.row_numbers, []).map(Number);
}

function allSkipped(rows: number[]) {
	return rows.every((row) => skippedRows.value.has(Number(row)));
}

// A value whose rows are all skipped needs no mapping.
function mapTo(mapping: DataImportValueMapping, value: string | null | undefined) {
	mapping.target_value = value || "";
	mapping.create_new = 0;
}

/** The server creates the record, named after the file's value, when the import runs. */
function createOnImport(mapping: DataImportValueMapping) {
	mapping.target_value = "";
	mapping.create_new = 1;
}

function isValueSkipped(mapping: DataImportValueMapping) {
	const rows = rowNumbers(mapping);
	return rows.length > 0 && allSkipped(rows);
}

function canSkipValue(mapping: DataImportValueMapping) {
	return !importStarted.value && rowNumbers(mapping).length > 0;
}

const skippableMappings = computed(() => doc.value.value_mappings.filter(canSkipValue));
const allValuesSkipped = computed(
	() => skippableMappings.value.length > 0 && skippableMappings.value.every(isValueSkipped)
);
const someValuesSkipped = computed(() => skippableMappings.value.some(isValueSkipped));

/** Skips every value's rows, or brings them all back when all are skipped already. */
function toggleSkipAll() {
	toggleSkipRows([...new Set(skippableMappings.value.flatMap(rowNumbers))]);
}

function canMap(mapping: DataImportValueMapping) {
	if (running.value) return false;
	const rows = rowNumbers(mapping);
	return !(rows.length && allSkipped(rows));
}

function isDuplicateId(warning: Warning) {
	return warning.type === "duplicate_id" && warning.rows?.length > 1;
}

function duplicateSkipped(warning: Warning) {
	return isDuplicateId(warning) && allSkipped(warning.rows.slice(1));
}

/** Skips every row in `rows`, or restores them when all are skipped already. */
function toggleSkipRows(rows: number[]) {
	const numbers = rows.map(Number);
	if (allSkipped(numbers)) {
		doc.value.skipped_rows = doc.value.skipped_rows.filter(
			(skipped) => !numbers.includes(Number(skipped.row_number))
		);
		return;
	}
	for (const row of numbers) {
		if (skippedRows.value.has(row)) continue;
		const cells = previewRow(row);
		doc.value.skipped_rows.push({
			row_number: row,
			row_data: JSON.stringify(cells ? cells.slice(1) : []),
		});
	}
}

function isSrNoColumn(col: Record<string, any>) {
	return col.header_title === "Sr. No" || col.header_title === t("Sr. No");
}

/** One warning per column (the longer message usually lists the rows); exact repeats dropped. */
function dedupeWarnings(list: Warning[]) {
	const rows: Warning[] = [];
	const seenRows = new Set<string>();
	const byColumn = new Map<unknown, Warning>();
	const others = new Map<string, Warning>();
	for (const warning of list) {
		if (warning.row) {
			const key = `${warning.row}|${warning.field?.fieldname}|${warning.message}`;
			if (seenRows.has(key)) continue;
			seenRows.add(key);
			rows.push(warning);
		} else if (warning.col) {
			const previous = byColumn.get(warning.col);
			if (!previous || (warning.message || "").length > (previous.message || "").length)
				byColumn.set(warning.col, warning);
		} else {
			const key = `${warning.code || ""}|${warning.title || ""}|${warning.message || ""}`;
			const existing = others.get(key);
			if (!existing || (warning.type && !existing.type)) others.set(key, warning);
		}
	}
	// Desk keeps columns in a plain object, so they come out in column order.
	const columnWarnings = [...byColumn.entries()]
		.sort(([a], [b]) => Number(a) - Number(b))
		.map(([, warning]) => warning);
	return [...rows, ...columnWarnings, ...others.values()];
}
</script>
