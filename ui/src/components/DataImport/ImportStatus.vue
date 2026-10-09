<template>
	<div v-if="headline.length || running" class="flex flex-col gap-3 px-5 pb-4">
		<Alert v-if="headline.length" data-slot="import-status" theme="blue" :title="headline[0]">
			<template v-if="headline.length > 1" #description>
				<div class="flex flex-col gap-1">
					<div v-for="line in headline.slice(1)" :key="line">{{ line }}</div>
				</div>
			</template>
		</Alert>
		<div v-if="running" class="flex flex-col gap-2">
			<Progress size="md" :value="percent" :label="t('Import Progress')" />
			<p class="text-sm text-ink-gray-6">{{ message }}</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Progress } from "frappe-ui";
import { computed } from "vue";
import { cint } from "./dataImport";
import { progressMessage, progressPercent } from "./importProgress";
import { t } from "./translate";
import { emptyProgress, type UseDataImport } from "./useDataImport";

const props = defineProps<{ dataImport: UseDataImport }>();

const { doc, running, importStatus } = props.dataImport;

const progress = computed(() => props.dataImport.progress.value ?? emptyProgress());
const percent = computed(() => progressPercent(progress.value));
const message = computed(() => progressMessage(doc.value, progress.value));

// Desk's show_import_status, which it shows as the form's headline.
const headline = computed(() => {
	const status = importStatus.value;
	if (doc.value.status === "Pending" || !status || !cint(status.total_records)) return [];
	const total = cint(status.total_records);
	const importType = doc.value.import_type;
	const lines: string[] = [];
	if (importType === "Update Existing Records")
		lines.push(
			t("Successfully updated {0} out of {1} records.", [cint(status.success), total])
		);
	else if (importType === "Insert or Update Records")
		lines.push(
			t("Successfully inserted {0} and updated {1} out of {2} records.", [
				cint(status.inserted),
				cint(status.updated),
				total,
			])
		);
	else
		lines.push(
			t("Successfully imported {0} out of {1} records.", [cint(status.success), total])
		);

	if (cint(status.failed) > 0)
		lines.push(
			t("Use 'Download Failed Rows' on the Failed metric, fix the errors and import again.")
		);
	if ((doc.value.skipped_rows || []).length)
		lines.push(
			t("Use 'Download Skipped Rows' on the Skipped metric to export the skipped rows.")
		);
	if (status.status === "Timed Out") lines.push(t("Import timed out, please re-try."));
	return lines;
});
</script>
