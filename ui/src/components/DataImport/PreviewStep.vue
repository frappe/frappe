<template>
	<div class="text-base h-full flex flex-col w-[90%] lg:w-[700px] mx-auto py-12 space-y-10">
		<div class="flex flex-col space-y-1">
			<div class="flex items-center justify-between text-ink-gray-7">
				<div class="flex items-center space-x-2 text-md font-semibold text-ink-gray-9">
					<span> Review and Import </span>

					<Badge :theme="getBadgeColor(data.status)">
						{{ data.status }}
					</Badge>
				</div>
				<Button
					v-if="data.status != 'Success'"
					:label="data.status != 'Pending' ? 'Retry' : 'Import'"
					variant="solid"
					@click="startImport"
				/>
				<Button v-else-if="listRoute" label="Done" @click="redirectToList()" />
			</div>
			<div class="leading-5 text-ink-gray-7">
				Verify the data before starting the import process
			</div>
		</div>

		<div v-if="mapping.length" class="space-y-2">
			<div class="text-ink-gray-5 text-sm">Column Mapping</div>
			<div class="border rounded-md bg-surface-gray-2 p-4 space-y-4 text-sm text-ink-gray-7">
				<div
					v-for="map in mapping"
					class="grid grid-cols-[40%,10%,40%] lg:grid-cols-3 space-x-3 items-center"
				>
					<div class="">
						{{ map[0] }}
					</div>
					<div class="flex justify-end">
						<FeatherIcon name="arrow-right" class="inline size-4 text-ink-gray-5" />
					</div>
					<div>
						{{ map[1] }}
					</div>
				</div>
			</div>
		</div>

		<div v-if="warnings.length" class="space-y-2">
			<div class="text-ink-gray-5 text-sm">Warnings</div>
			<div class="rounded-md bg-surface-amber-2 p-2 space-y-2 text-xs">
				<div v-for="warning in warnings" class="flex items-center space-x-2">
					<FeatherIcon name="alert-circle" class="size-3 text-ink-amber-6" />
					<div v-html="warning.message" class="text-ink-amber-6"></div>
				</div>
			</div>
		</div>

		<div v-if="preview?.data?.length" class="border rounded-md overflow-x-auto">
			<table class="divide-y">
				<thead class="rounded-t-md">
					<tr>
						<th
							v-for="column in previewColumns"
							:key="column.key"
							:style="{ minWidth: column.width, textAlign: column.align }"
							class="p-2 text-left text-sm text-ink-gray-5"
							:class="{
								'border-r':
									column.key != previewColumns[previewColumns.length - 1].key,
								'w-full':
									column.key == previewColumns[previewColumns.length - 1].key,
							}"
						>
							{{ column.label }}
						</th>
					</tr>
				</thead>
				<tbody class="bg-surface-base divide-y divide-outline-gray-1">
					<tr v-for="(row, rowIndex) in previewData" :key="rowIndex">
						<td
							v-for="column in previewColumns"
							:key="column.key"
							:style="{ minWidth: column.width, textAlign: column.align }"
							class="px-3 py-2 text-sm text-ink-gray-7 align-top"
							:class="{
								'border-r':
									column.key != previewColumns[previewColumns.length - 1].key,
							}"
						>
							<div class="leading-5 text-sm">
								{{ row[column.key] }}
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-if="data.status != 'Pending' && importLogs.length" class="space-y-4">
			<div class="font-semibold text-ink-gray-9">Import Logs</div>

			<div class="rounded-md p-2" :class="importBannerClass">
				{{ importSuccessCount }} {{ importSuccessCount == 1 ? "row" : "rows" }} imported
				successfully, {{ importErrorCount }}
				{{ importErrorCount == 1 ? "row" : "rows" }} failed.
			</div>

			<TabButtons :buttons="tabButtons" v-model="activeTab" class="w-fit" />

			<div v-if="filteredLogs.length" class="border rounded-md overflow-x-auto">
				<table class="table-fixed w-full divide-y">
					<thead class="rounded-t-md">
						<tr>
							<th
								class="p-2 text-left text-sm text-ink-gray-5 w-20 border-r text-center"
							>
								Row no.
							</th>
							<th class="p-2 text-left text-sm text-ink-gray-5 w-[80%]">Message</th>
						</tr>
					</thead>
					<tbody class="bg-surface-base divide-y divide-outline-gray-1">
						<tr v-for="(row, rowIndex) in filteredLogs" :key="rowIndex" class="group">
							<td class="px-3 py-2 text-sm text-ink-gray-7 border-r">
								<div class="flex items-center justify-center space-x-2">
									<div
										v-if="row.success"
										class="size-1.5 bg-surface-green-3 rounded"
									></div>
									<div v-else class="size-1.5 bg-surface-red-7 rounded"></div>
									<div>
										{{ JSON.parse(row["row_indexes"])[0] - 1 }}
									</div>
								</div>
							</td>

							<td class="px-3 py-2 text-sm text-ink-gray-7 w-full">
								<span v-if="rowMessage(row)" v-html="rowMessage(row)"> </span>
								<span v-else-if="!rowMessage(row) && !row.success">
									Failed to import
								</span>
								<span v-else-if="row.success">
									Successfully imported
									<span
										@click="redirectToPage(row.docname)"
										:class="{
											'cursor-pointer underline': pageRoute,
										}"
									>
										{{ row.docname }}
									</span>
								</span>
							</td>
							<td
								class="px-3 py-2 text-ink-gray-5 float-right invisible group-hover:visible"
							>
								<HoverCard v-if="row.exception" side="left" align="start">
									<template #trigger>
										<FeatherIcon name="info" class="size-4" />
									</template>
									<div class="w-[500px] p-2 text-xs leading-5 font-mono">
										{{ row.exception }}
									</div>
								</HoverCard>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div v-else class="text-ink-gray-5 text-sm">No logs to display.</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { getPreviewData, getBadgeColor } from "./dataImport";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { DataImport, DataImports, DataImportSocket } from "./types";
import { Badge, Button, FeatherIcon, HoverCard, TabButtons, call } from "frappe-ui";

const preview = ref<any>(null);
const emit = defineEmits(["updateStep"]);
const importLogs = ref<any[]>([]);
const filteredLogs = ref<any[]>([]);
const activeTab = ref("all");

const props = defineProps<{
	dataImports: DataImports;
	data: DataImport;
	fields: any;
	doctypeMap: Record<string, { title: string; listRoute?: string; pageRoute?: string }>;
	socket?: DataImportSocket;
}>();

const onImportRefresh = (data: { data_import: string }) => {
	reloadPreviewData(data.data_import);
};

onMounted(async () => {
	// The host owns the socket connection, the same way `useNotifications` takes
	// one. Without it the table still loads; it just does not refresh itself
	// while the import runs.
	props.socket?.on("data_import_refresh", onImportRefresh);

	if (!props.data?.name) return;
	preview.value = await getPreviewData(
		props.data.name,
		props.data.import_file,
		props.data.google_sheets_url
	);
	if (props.data.status != "Pending") {
		getImportLogs();
	}
});

onBeforeUnmount(() => {
	// The socket is the host's and outlives this screen, so drop our listener.
	props.socket?.off("data_import_refresh", onImportRefresh);
});

const reloadPreviewData = (dataImport: string) => {
	if (dataImport != props.data.name) return;
	nextTick(() => {
		props.dataImports.reload();
		nextTick(async () => {
			let updatedData = props.dataImports.data?.find((d) => d.name === props.data.name);
			emit("updateStep", "preview", { ...updatedData });
			getImportLogs();
		});
	});
};

const previewColumns = computed(() => {
	const columns: any[] = [];
	preview.value?.columns.forEach((col: any, index: number) => {
		let align = "left";
		let width = "300px";
		if (index == 0) {
			col.header_title = "No";
			align = "center";
			width = "60px";
		} else if (col.header_title == "ID") {
			width = "150px";
		}
		columns.push({
			key: col.header_title,
			label: col.header_title,
			width: width,
			align: align,
		});
	});
	return columns;
});

const previewData = computed(() => {
	const data: Record<string, any>[] = [];
	preview.value?.data.forEach((row: any) => {
		const dataMap: Record<string, any> = {};
		Object.keys(row).forEach((key: any, index: number) => {
			let columnLabel = getColumnLabel(index);
			let mappedFieldIndex = getMappedColumnName(index);
			if (columnLabel == "No") {
				dataMap[columnLabel] = row[key] - 1;
			} else if (mappedFieldIndex) {
				dataMap[columnLabel] = row[mappedFieldIndex];
			} else {
				dataMap[columnLabel] = row[key];
			}
		});
		data.push(dataMap);
	});
	return data;
});

const getColumnLabel = (index: number) => {
	return preview.value?.columns[index]?.header_title || `Column ${index + 1}`;
};

const getMappedColumnName = (index: number) => {
	let mappedColumn = preview.value?.columns[index]?.map_to_field;
	if (!mappedColumn) return null;
	let mappedColumnLabel = preview.value?.columns[index]?.df?.label;
	let mappedColumnIndex = preview.value?.columns.filter(
		(col: any) => col.header_title == mappedColumnLabel
	)[0]?.column_number;
	return mappedColumnIndex;
};

const startImport = () => {
	call("frappe.core.doctype.data_import.data_import.form_start_import", {
		data_import: props.data.name,
	});
};

const getImportLogs = () => {
	call("frappe.core.doctype.data_import.data_import.get_import_logs", {
		data_import: props.data.name,
	}).then((data: any) => {
		importLogs.value = data;
		filteredLogs.value = data;
	});
};

const updateImportLogs = () => {
	if (activeTab.value == "all") {
		filteredLogs.value = importLogs.value;
	} else if (activeTab.value == "successful") {
		filteredLogs.value = importLogs.value.filter((log) => log.success);
	} else if (activeTab.value == "failed") {
		filteredLogs.value = importLogs.value.filter((log) => !log.success);
	}
};

watch(activeTab, () => {
	updateImportLogs();
});

const importSuccessCount = computed(() => {
	if (!importLogs.value.length) return 0;
	return importLogs.value.filter((log) => log.success).length;
});

const importErrorCount = computed(() => {
	if (!importLogs.value.length) return 0;
	return importLogs.value.filter((log) => !log.success).length;
});

const importBannerClass = computed(() => {
	if (importErrorCount.value == 0) {
		return "bg-surface-green-2 text-ink-green-6";
	} else if (importSuccessCount.value == 0) {
		return "bg-surface-red-2 text-ink-red-6";
	} else {
		return "bg-surface-amber-2 text-ink-amber-6";
	}
});

const mapping = computed(() => {
	let warningMap: string[][] = [];
	if (!preview.value?.warnings?.length) return [];
	preview.value.warnings.forEach((warning: any) => {
		if (warning.type == "info") {
			const regex = /<strong>(.*?)<\/strong>/g;
			let match;
			const fields = [];
			while ((match = regex.exec(warning.message)) !== null) {
				fields.push(match[1]);
			}
			warningMap.push(fields);
		}
	});
	return warningMap;
});

const warnings = computed(() => {
	return preview.value?.warnings?.filter((warning: any) => warning.type != "info") || [];
});

const listRoute = computed(() => {
	return props.doctypeMap[props.data.reference_doctype]?.listRoute;
});

const redirectToList = () => {
	if (!listRoute.value) return;
	window.location.href = listRoute.value;
};

const pageRoute = computed(() => {
	return props.doctypeMap[props.data.reference_doctype]?.pageRoute;
});

const redirectToPage = (docname: string) => {
	if (!pageRoute.value) return;
	window.location.href = pageRoute.value.replace("docname", docname);
};

const tabButtons = computed(() => {
	return [
		{ label: "All", value: "all" },
		{ label: "Successful", value: "successful" },
		{ label: "Failed", value: "failed" },
	];
});

const rowMessage = (row: any) => {
	return JSON.parse(row.messages)?.[0]?.message;
};
</script>
