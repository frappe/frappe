<template>
	<div v-if="running" class="flex flex-col gap-4">
		<div class="flex flex-col gap-2">
			<div class="flex items-start justify-between gap-4">
				<div class="flex min-w-0 flex-col gap-0.5">
					<h3 class="text-base-medium text-ink-gray-8">
						{{ t("Importing your data") }}
					</h3>
					<p class="text-sm text-ink-gray-6">
						{{
							t(
								"You can continue other work while this runs. Progress updates will appear here."
							)
						}}
					</p>
				</div>
				<span class="shrink-0 text-base-medium text-ink-gray-8">{{ percent }}%</span>
			</div>
			<Progress size="md" :value="percent" />
			<div class="flex items-center justify-between gap-4 text-sm">
				<span class="text-ink-gray-7">{{ rowProgress }}</span>
				<span class="text-ink-gray-6">{{ statusLine }}</span>
			</div>
		</div>

		<StatCards :stats="statCards" :label="t('Progress summary')" />

		<div class="flex flex-col gap-1">
			<div class="flex items-center gap-1">
				<span class="text-sm-semibold text-ink-gray-7">{{ t("Recent activity") }}</span>
				<span class="lucide-dot size-4 text-ink-green-8" />
			</div>
			<ul class="flex flex-col">
				<li
					v-for="(item, index) in progress.recentActivity"
					:key="index"
					class="flex items-center gap-2 py-1"
					:class="{ 'border-t border-outline-gray-1': index > 0 }"
				>
					<span class="size-4 shrink-0" :class="activityIcon(item.kind)" />
					<span
						v-if="item.isHtml"
						class="min-w-0 flex-1 truncate text-sm text-ink-gray-7"
						v-html="item.text"
					/>
					<span v-else class="min-w-0 flex-1 truncate text-sm text-ink-gray-7">{{
						item.text
					}}</span>
					<span
						v-if="item.row"
						class="shrink-0 whitespace-nowrap text-sm text-ink-gray-6"
					>
						{{ t("Row {0}", [item.row]) }}
					</span>
				</li>
				<li v-if="!progress.recentActivity.length" class="py-1 text-sm text-ink-gray-6">
					{{ t("Live activity updates will appear here.") }}
				</li>
			</ul>
		</div>
	</div>

	<div v-else-if="importStarted && !importStatus" class="flex flex-col gap-3" aria-busy="true">
		<Skeleton class="h-24 w-full rounded-5" />
		<Skeleton class="h-7 w-60 rounded-full" />
		<Skeleton class="h-40 w-full rounded-5" />
	</div>

	<div v-else-if="importStarted" class="flex flex-col gap-4">
		<div class="flex flex-col gap-3">
			<StatCards :stats="resultStats" :label="t('Result')" />

			<div class="flex items-center justify-between gap-4">
				<dl class="flex min-w-0 flex-wrap gap-x-6 gap-y-1 text-sm text-ink-gray-6">
					<div v-for="row in detailRows" :key="row.label" class="flex gap-1">
						<dt>{{ row.label }}</dt>
						<dd class="flex gap-1">
							<button
								type="button"
								class="text-ink-gray-7 hover:underline"
								@click="emit('openRecord', 'User', row.user)"
							>
								{{ fullNames[row.user] || row.user }}
							</button>
							<span>·</span>
							<span>{{ row.date }}</span>
						</dd>
					</div>
				</dl>
				<Button
					v-if="isFinished"
					class="shrink-0"
					variant="outline"
					size="sm"
					:label="t('Go to list')"
					icon-right="lucide-arrow-up-right"
					@click="emit('openList', doc.reference_doctype)"
				/>
			</div>
		</div>

		<div class="flex items-center justify-between gap-2">
			<TabButtons
				v-model="logFilter"
				:options="filterOptions"
				:aria-label="t('Filter import log')"
			/>
			<Button
				v-if="showExport"
				variant="outline"
				size="sm"
				:label="t('Export Import Log')"
				icon-left="lucide-download"
				@click="download('download_import_log')"
			/>
		</div>

		<table v-if="logs.length" class="w-full">
			<thead>
				<tr class="text-left text-ink-gray-6">
					<th class="w-[10%] border-b border-outline-gray-2 px-4 py-2 text-sm-semibold">
						{{ t("Row") }}
					</th>
					<th class="w-[14%] border-b border-outline-gray-2 px-4 py-2 text-sm-semibold">
						{{ t("Status") }}
					</th>
					<th class="w-[76%] border-b border-outline-gray-2 px-4 py-2 text-sm-semibold">
						{{ t("Message") }}
					</th>
				</tr>
			</thead>
			<tbody class="text-ink-gray-8">
				<tr v-for="(row, index) in logRows" :key="index">
					<td
						class="whitespace-nowrap border-b border-outline-gray-2 px-4 py-2 align-top text-sm"
					>
						{{ row.rowLabel }}
					</td>
					<td class="border-b border-outline-gray-2 px-4 py-2 align-top text-sm">
						<Badge
							:label="row.success ? t('Success') : t('Failure')"
							:theme="row.success ? 'green' : 'red'"
						/>
					</td>
					<td
						class="break-words border-b border-outline-gray-2 px-4 py-2 align-top text-sm"
					>
						<div v-if="row.success">
							<span>{{ row.successText[0] }}</span>
							<button
								type="button"
								class="underline"
								@click="emit('openRecord', doc.reference_doctype, row.docname)"
							>
								{{ row.docname }}
							</button>
							<span>{{ row.successText[1] }}</span>
						</div>
						<template v-else>
							<div class="flex items-center justify-between gap-2">
								<div v-if="row.summaryHtml" v-html="row.summaryHtml" />
								<div v-else>{{ row.summaryText }}</div>
								<Button
									v-if="row.expandable"
									variant="ghost"
									size="sm"
									:icon="
										expanded.has(index)
											? 'lucide-chevron-up'
											: 'lucide-chevron-down'
									"
									:title="t('Toggle error details')"
									:aria-label="t('Toggle error details')"
									:aria-expanded="expanded.has(index)"
									@click="toggle(index)"
								/>
							</div>
							<div v-if="expanded.has(index)">
								<div v-for="(detail, i) in row.details" :key="i">
									<div v-if="detail.title">
										<strong>{{ detail.title }}</strong>
									</div>
									<div v-if="detail.message" v-html="detail.message" />
								</div>
								<pre
									v-if="row.traceback"
									class="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-4 bg-surface-gray-2 p-2 text-sm"
									>{{ row.traceback }}</pre
								>
							</div>
						</template>
					</td>
				</tr>
			</tbody>
		</table>
		<div
			v-else
			class="flex min-h-32 flex-col items-center justify-center gap-2 text-ink-gray-6"
		>
			<span class="lucide-inbox size-6" />
			<span class="text-base">{{ emptyMessage }}</span>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button, Progress, Skeleton, TabButtons, call } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { dateFormat } from "../../ActivityTimeline/utils";
import { cint, parseJson, postDownload } from "../dataImport";
import {
	etaMessage,
	hasProgressCounts,
	notStartedMessage,
	progressPercent,
} from "../importProgress";
import { t } from "../translate";
import StatCards, { type Stat } from "./StatCards.vue";
import type { DataImportLog } from "../types";
import { emptyProgress, type UseDataImport } from "../useDataImport";

const LOG_LIMIT = 1000;
const METHODS = "frappe.core.doctype.data_import.data_import";
const UPSERT = "Insert or Update Records";

const props = defineProps<{ dataImport: UseDataImport }>();

const emit = defineEmits<{
	openList: [doctype: string];
	openRecord: [doctype: string, name: string];
}>();

const { doc, running, importStarted, importStatus, logFilter, logs } = props.dataImport;

// Finished either way, so the way back to the records is always there.
const isFinished = computed(
	() =>
		!running.value &&
		["Success", "Partial Success", "Error", "Timed Out"].includes(doc.value.status)
);

const progress = computed(() => props.dataImport.progress.value ?? emptyProgress());

const showInserted = computed(() =>
	[UPSERT, "Insert New Records"].includes(doc.value.import_type)
);
const showUpdated = computed(() =>
	[UPSERT, "Update Existing Records"].includes(doc.value.import_type)
);
const skippedCount = computed(() => (doc.value.skipped_rows || []).length);

const percent = computed(() => progressPercent(progress.value));
const rowProgress = computed(() =>
	hasProgressCounts(progress.value)
		? t("Importing row {0} of {1}", [progress.value.current, progress.value.total])
		: notStartedMessage(doc.value)
);
const statusLine = computed(() => {
	const { current, total, eta } = progress.value;
	if (!hasProgressCounts(progress.value))
		return doc.value.status === "Pending"
			? t("Preparing import...")
			: t("Fetching latest status...");
	return current >= total ? t("Finishing up...") : etaMessage(eta);
});

const statCards = computed(() => {
	const cards: Stat[] = [];
	if (showInserted.value) cards.push({ label: t("Inserted"), value: progress.value.inserted });
	if (showUpdated.value) cards.push({ label: t("Updated"), value: progress.value.updated });
	cards.push({ label: t("Skipped"), value: skippedCount.value });
	cards.push({
		label: t("Failed"),
		value: progress.value.failed,
		class: progress.value.failed ? "text-ink-red-6" : undefined,
	});
	return cards;
});

function activityIcon(kind: string) {
	if (kind === "success") return "lucide-circle-check text-ink-green-8";
	if (kind === "error") return "lucide-circle-alert text-ink-red-6";
	return "lucide-circle-minus text-ink-gray-6";
}

const rowIndexes = (log: DataImportLog) =>
	parseJson<unknown[]>(log.row_indexes, [])
		.map((row) => cint(row))
		.filter(Boolean);
const rowCount = (log: DataImportLog) => Math.max(rowIndexes(log).length, 1);
const sumRows = (filter: (log: DataImportLog) => boolean) =>
	logs.value.reduce((total, log) => total + (filter(log) ? rowCount(log) : 0), 0);

// Counts follow Desk's render_import_log: the status summary when it has any,
// otherwise counted from the log rows loaded for the current tab.
const counts = computed(() => {
	const summary = importStatus.value || ({} as Record<string, unknown>);
	const totalRecords = cint(summary.total_records);
	const success = cint(summary.success);
	const failed = cint(summary.failed);
	const hasSummary = totalRecords > 0 || success > 0 || failed > 0;

	const successRows = hasSummary ? success : sumRows((log) => !!log.success);
	const failedRows = hasSummary ? failed : sumRows((log) => !log.success);
	const totalRows = successRows + failedRows;
	const totalRowsInFile = hasSummary
		? Math.max(totalRecords, totalRows + skippedCount.value)
		: totalRows + skippedCount.value;

	let inserted = cint(summary.inserted);
	let updated = cint(summary.updated);
	if (doc.value.import_type !== UPSERT) {
		inserted = doc.value.import_type === "Insert New Records" ? successRows : 0;
		updated = doc.value.import_type === "Update Existing Records" ? successRows : 0;
	} else if (!inserted && !updated) {
		inserted = sumRows((log) => !!log.success && log.import_action === "Insert");
		updated = sumRows((log) => !!log.success && log.import_action === "Update");
	}
	return { successRows, failedRows, totalRows, totalRowsInFile, inserted, updated };
});

const showExport = computed(
	() =>
		counts.value.totalRows > LOG_LIMIT ||
		counts.value.successRows > LOG_LIMIT ||
		counts.value.failedRows > LOG_LIMIT
);

const resultStats = computed(() => {
	const stats: Stat[] = [{ label: t("Total rows"), value: counts.value.totalRowsInFile }];
	if (showInserted.value) stats.push({ label: t("Inserted"), value: counts.value.inserted });
	if (showUpdated.value) stats.push({ label: t("Updated"), value: counts.value.updated });
	stats.push({
		label: t("Skipped"),
		value: skippedCount.value,
		download: skippedCount.value
			? {
					title: t("Download Skipped Rows"),
					onClick: () => download("download_skipped_rows"),
			  }
			: undefined,
	});
	stats.push({
		label: t("Failed"),
		value: counts.value.failedRows,
		class: counts.value.failedRows ? "text-ink-red-6" : undefined,
		download: counts.value.failedRows
			? {
					title: t("Download Failed Rows"),
					onClick: () => download("download_errored_template"),
			  }
			: undefined,
	});
	return stats;
});

const fullNames = ref<Record<string, string>>({});

watch(
	() => [doc.value.owner, doc.value.modified_by],
	async (users) => {
		const missing = [...new Set(users)].filter(
			(user): user is string => !!user && !(user in fullNames.value)
		);
		if (!missing.length) return;
		const rows = await call<{ name: string; full_name: string }[]>("frappe.client.get_list", {
			doctype: "User",
			fields: ["name", "full_name"],
			filters: { name: ["in", missing] },
		}).catch(() => []);
		for (const { name, full_name } of rows) fullNames.value[name] = full_name || name;
	},
	{ immediate: true }
);

const detailRows = computed(() => {
	const date = (value?: string) => (value ? dateFormat(value) : "-");
	return [
		{ label: t("Started by"), user: doc.value.owner, date: date(doc.value.creation) },
		{
			label: t("Last modified by"),
			user: doc.value.modified_by,
			date: date(doc.value.modified),
		},
	].filter((row): row is { label: string; user: string; date: string } => !!row.user);
});

const tabCount = (total: number) =>
	total > LOG_LIMIT ? t("{0} of {1}", [LOG_LIMIT, total]) : String(total);

const filterOptions = computed(() => [
	{ label: t("All ({0})", [tabCount(counts.value.totalRows)]), value: "all" },
	{ label: t("Success ({0})", [tabCount(counts.value.successRows)]), value: "success" },
	{ label: t("Failed ({0})", [tabCount(counts.value.failedRows)]), value: "failed" },
]);

const emptyMessage = computed(() => {
	if (logFilter.value === "failed") return t("No failed log entries");
	if (logFilter.value === "success") return t("No successful log entries");
	return t("No rows were imported");
});

const normalize = (value?: string) => (value || "").replace(/\s+/g, " ").trim().toLowerCase();

// The record name sits inside a translated sentence, so translate the whole
// sentence around a marker and render the link where the marker was.
const LINK_MARKER = "\u0000";
function successText(log: DataImportLog): [string, string] {
	let message = "Successfully imported {0}";
	if (doc.value.import_type === UPSERT)
		message =
			log.import_action === "Update"
				? "Successfully updated {0}"
				: "Successfully inserted {0}";
	else if (doc.value.import_type === "Update Existing Records")
		message = "Successfully updated {0}";
	const [before = "", after = ""] = t(message, [LINK_MARKER]).split(LINK_MARKER);
	return [before, after];
}

const logRows = computed(() =>
	logs.value.map((log) => {
		const indexes = rowIndexes(log);
		const base = {
			success: !!log.success,
			rowLabel: indexes.length ? indexes.join(", ") : t("-"),
			docname: log.docname || "",
			successText: ["", ""] as [string, string],
			summaryHtml: "",
			summaryText: "",
			details: [] as { title?: string; message?: string }[],
			traceback: "",
			expandable: false,
		};
		if (log.success) return { ...base, successText: successText(log) };

		const messages = parseJson<{ title?: string; message?: string }[]>(log.messages, []);
		const first = messages[0];
		const summary = normalize(first?.message || first?.title || t("Import failed"));
		const details = messages.filter((m) => {
			const text = normalize(m.message || m.title);
			return text && text !== summary;
		});
		// A readable message already says what to fix; the traceback only helps
		// with unexpected failures. It stays in the exported import log.
		const traceback = first ? "" : (log.exception || "").trim();
		return {
			...base,
			// message is cleaned on the server; title is not, so it goes in as text
			summaryHtml: first?.message || "",
			summaryText: first?.title || t("Import failed"),
			details,
			traceback,
			expandable: !!(details.length || traceback),
		};
	})
);

const expanded = ref(new Set<number>());
watch(logs, () => (expanded.value = new Set()));

function toggle(index: number) {
	const next = new Set(expanded.value);
	if (!next.delete(index)) next.add(index);
	expanded.value = next;
}

function download(method: string) {
	postDownload(`/api/method/${METHODS}.${method}`, { data_import_name: doc.value.name || "" });
}
</script>
