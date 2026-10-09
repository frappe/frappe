<template>
	<div class="mx-auto flex min-h-0 w-full max-w-[700px] flex-col gap-5 px-4 py-5 text-base">
		<div class="flex items-center justify-between gap-4">
			<div class="text-ink-gray-6">
				{{ t("Import data into your system using CSV files.") }}
			</div>
			<Button
				variant="solid"
				:label="t('Import')"
				icon-left="lucide-plus"
				@click="emit('new')"
			/>
		</div>

		<div class="flex items-center gap-2">
			<FormControl
				v-model="search"
				:placeholder="t('Search imported files')"
				type="text"
				class="flex-1"
			/>
			<div class="w-44 shrink-0">
				<FormControl v-model="status" type="select" :options="statusOptions" />
			</div>
		</div>

		<div v-if="rows.length" class="flex flex-col gap-5 overflow-y-auto">
			<div class="flex flex-col divide-y divide-outline-gray-1">
				<div
					class="grid grid-cols-[1fr_7rem_8rem] items-center px-3 py-1.5 text-sm text-ink-gray-6"
				>
					<div>{{ t("Document Type") }}</div>
					<div>{{ t("Import Type") }}</div>
					<div class="ps-1">{{ t("Status") }}</div>
				</div>
				<div
					v-for="row in rows"
					:key="row.name"
					class="grid cursor-pointer grid-cols-[1fr_7rem_8rem] items-center px-3 py-2.5"
					@click="emit('open', row.name)"
				>
					<div class="flex flex-col gap-1">
						<div class="text-ink-gray-8">
							{{ row.reference_doctype }}
						</div>
						<div class="text-ink-gray-6">
							{{ dayjs(row.creation).fromNow() }}
						</div>
					</div>
					<div class="text-ink-gray-8">{{ importTypeLabel(row.import_type) }}</div>
					<Badge
						:label="t(row.status)"
						:theme="getBadgeColor(row.status) as BadgeProps['theme']"
						class="w-fit"
					/>
				</div>
			</div>
			<div v-if="hasNextPage" class="flex justify-center">
				<Button :label="t('Load More')" icon-left="lucide-refresh-cw" @click="loadMore" />
			</div>
		</div>
		<div v-else-if="!loading" class="text-ink-gray-6">
			{{ t("No data imports found.") }}
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, FormControl, dayjs } from "frappe-ui";
import type { BadgeProps } from "frappe-ui";
import { getBadgeColor } from "./dataImport";
import { t } from "./translate";
import type { DataImportType } from "./types";
import type { DataImportListStatus, UseDataImportList } from "./useDataImportList";

const props = defineProps<{ list: UseDataImportList }>();
const emit = defineEmits<{ open: [name: string]; new: [] }>();

const { search, status, rows, loading, hasNextPage, loadMore } = props.list;

const statusOptions = computed(() => {
	const statuses: DataImportListStatus[] = [
		"All",
		"Pending",
		"In Progress",
		"Success",
		"Partial Success",
		"Error",
		"Timed Out",
	];
	return statuses.map((value) => ({ label: t(value), value }));
});

function importTypeLabel(importType: DataImportType) {
	return {
		"Insert New Records": t("Insert"),
		"Update Existing Records": t("Update"),
		"Insert or Update Records": t("Upsert"),
	}[importType];
}
</script>
