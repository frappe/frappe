<template>
	<div class="flex h-full w-full min-w-0 flex-col gap-5">
		<ol data-slot="steps" class="grid w-full grid-cols-4 gap-1">
			<li
				v-for="(step, index) in steps"
				:key="step.label"
				class="flex min-w-0 flex-col gap-2"
				:aria-current="index === current ? 'step' : undefined"
			>
				<button
					type="button"
					data-slot="step"
					class="group flex w-full min-w-0 flex-col gap-2 rounded text-start focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 disabled:cursor-default"
					:disabled="step.locked || index === current"
					@click="goTo(index)"
				>
					<span
						class="flex min-w-0 items-center gap-1.5 text-base"
						:class="
							index === current
								? 'font-medium text-ink-gray-8'
								: step.completed
								? 'text-ink-gray-7 group-enabled:group-hover:text-ink-gray-9'
								: 'text-ink-gray-5 group-enabled:group-hover:text-ink-gray-7'
						"
					>
						<span class="truncate">{{ step.label }}</span>
					</span>
					<span
						class="block h-1 w-full rounded-7"
						:class="
							index === current || step.completed
								? 'bg-surface-gray-10'
								: 'bg-surface-gray-2'
						"
					/>
				</button>
			</li>
		</ol>

		<div
			v-if="!(loading && isNew)"
			class="flex min-h-0 w-full min-w-0 flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base"
		>
			<div class="min-h-0 w-full min-w-0 flex-1 overflow-auto px-5 py-4">
				<component
					:is="stepComponents[current]"
					:dataImport="dataImport"
					:showErrors="current === CONFIG ? showConfigErrors : undefined"
					v-on="stepEvents[current] ?? {}"
				/>
			</div>

			<ImportStatus v-if="!(current === IMPORT && running)" :dataImport="dataImport" />

			<div
				class="flex w-full items-center justify-between border-t border-outline-gray-2 px-5 py-4"
			>
				<div>
					<Button
						v-if="current !== CONFIG"
						:label="t('Back')"
						icon-left="lucide-arrow-left"
						@click="goTo(current - 1)"
					/>
				</div>
				<div class="flex items-center gap-2">
					<Button
						v-if="showNext"
						:label="t('Next')"
						icon-right="lucide-arrow-right"
						:loading="previewLoading"
						:loading-text="t('Loading preview...')"
						@click="goTo(current + 1)"
					/>
					<Button
						v-if="showImport"
						variant="solid"
						:label="rowsToSkip.length ? t('Skip all and import') : t('Import')"
						:loading="starting || saving || previewLoading"
						:loading-text="previewLoading ? t('Loading preview...') : t('Starting...')"
						@click="skipErrorRowsAndImport"
					/>
					<template v-if="current === IMPORT">
						<Button
							v-if="running"
							:label="t('Cancel Import')"
							icon-left="lucide-x"
							@click="confirmingStop = true"
						/>
						<template v-else-if="isFinished">
							<Button
								v-if="canRetry"
								:variant="retryFirst ? 'solid' : 'outline'"
								:label="t('Retry')"
								icon-left="lucide-refresh-cw"
								:loading="retrying"
								:loading-text="t('Retrying...')"
								@click="retryImport"
							/>
							<Button
								v-if="onNewImport"
								:variant="newImportFirst ? 'solid' : 'outline'"
								:label="t('Start new import')"
								icon-left="lucide-plus"
								@click="onNewImport(doc.reference_doctype)"
							/>
						</template>
					</template>
				</div>
			</div>
		</div>

		<Dialog
			v-model:open="confirmingStop"
			:title="t('Confirm')"
			:message="
				t('This will terminate the job immediately and might be dangerous, are you sure?')
			"
			:actions="[
				{ label: t('Yes'), variant: 'solid', onClick: stopImport },
				{ label: t('No'), onClick: ({ close }) => close() },
			]"
		/>
	</div>
</template>

<script setup lang="ts">
import { Button, Dialog, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import ImportStatus from "./ImportStatus.vue";
import { errorRowNumbers, skipRows } from "./dataImport";
import ConfigStep from "./steps/ConfigStep.vue";
import FixIssuesStep from "./steps/FixIssuesStep.vue";
import ImportStep from "./steps/ImportStep.vue";
import PreviewStep from "./steps/PreviewStep.vue";
import { t } from "./translate";
import type { UseDataImport } from "./useDataImport";
import {
	CONFIG,
	FIX_ISSUES,
	IMPORT,
	PREVIEW,
	canGoToStep,
	isStepCompleted,
	landingStep,
} from "./wizardSteps";

const props = defineProps<{
	dataImport: UseDataImport;
	// A prop, not an emit, so "Start new import" only shows when the app handles it.
	onNewImport?: (doctype: string) => void;
}>();

const emit = defineEmits<{
	openList: [doctype: string];
	openRecord: [doctype: string, name: string];
	openImports: [doctype: string];
}>();

const openList = (doctype: string) => emit("openList", doctype);
const openRecord = (doctype: string, name: string) => emit("openRecord", doctype, name);
const openImports = (doctype: string) => emit("openImports", doctype);
// Only the Config and Import steps link back to the app.
const stepEvents: Record<number, Record<string, (...args: any[]) => void>> = {
	[CONFIG]: { openImports },
	[IMPORT]: { openList, openRecord },
};

const {
	doc,
	isNew,
	dirty,
	loading,
	saving,
	hasImportFile,
	preview,
	previewReady,
	previewLoading,
	running,
	importStarted,
	blocked,
} = props.dataImport;

const stepComponents = [ConfigStep, PreviewStep, FixIssuesStep, ImportStep];

const current = ref(CONFIG);
const confirmingStop = ref(false);
// Saving and asking the server to start; on a developer site the whole run happens in that request.
const starting = ref(false);
// Config marks what is missing once Next is pressed without it.
const showConfigErrors = ref(false);

const stepState = computed(() => ({
	isNew: isNew.value,
	hasImportFile: hasImportFile.value,
	importStarted: importStarted.value,
}));

const steps = computed(() =>
	[t("Config"), t("Map columns"), t("Fix issues"), t("Import")].map((label, index) => ({
		label,
		completed: isStepCompleted(index, current.value, doc.value, stepState.value),
		locked: !canGoToStep(index, current.value, doc.value, stepState.value),
	}))
);

const canImport = computed(
	() => !isNew.value && hasImportFile.value && doc.value.status !== "Success"
);
const showNext = computed(
	() =>
		current.value === CONFIG ||
		current.value === PREVIEW ||
		(current.value === FIX_ISSUES && importStarted.value)
);
const showImport = computed(
	() => current.value === FIX_ISSUES && canImport.value && !importStarted.value
);
const canRetry = computed(() =>
	["Error", "Partial Success", "Timed Out"].includes(doc.value.status)
);
const isFinished = computed(() => canRetry.value || doc.value.status === "Success");
// A timeout may pass on a second try; failed rows fail again until the file is fixed.
const retryFirst = computed(() => doc.value.status === "Timed Out" || !props.onNewImport);
const newImportFirst = computed(() => !canRetry.value || !retryFirst.value);

// Synchronous, so `saving` still tells a first save (stay on the step) from
// another import being opened (go to its landing step).
watch(
	() => doc.value.name,
	() => {
		if (!saving.value) current.value = landingStep(doc.value);
	},
	{ immediate: true, flush: "sync" }
);

watch(blocked, (isBlocked) => {
	if (!isBlocked) return;
	toast.error(t("Import could not start. Please resolve the errors in the import file."));
	current.value = FIX_ISSUES;
});

async function saveIfDirty() {
	if (!dirty.value) return true;
	try {
		await props.dataImport.save();
		return true;
	} catch {
		return false;
	}
}

/** Back moves freely; going forward saves first and checks the step can open. */
async function goTo(target: number) {
	const from = current.value;
	if (target <= from) {
		current.value = target;
		return;
	}
	// Checked before saving, so a new import is never saved without a file.
	if (
		!doc.value.reference_doctype ||
		!doc.value.import_type ||
		(from <= PREVIEW && !hasImportFile.value)
	) {
		showConfigErrors.value = true;
		current.value = CONFIG;
		return;
	}
	if (!(await saveIfDirty())) return;
	// The preview step shows its own loading state, so open it before the fetch.
	if (from === CONFIG && target === PREVIEW) current.value = PREVIEW;

	if (hasImportFile.value && !previewReady.value) {
		await props.dataImport.fetchPreview();
		if (!previewReady.value) {
			// The Map columns step shows why the preview failed.
			current.value = PREVIEW;
			return;
		}
	}
	if (target === IMPORT && !importStarted.value) {
		toast.warning(t("Start the import before opening the Import step."));
		return;
	}
	current.value = target;
}

// A row error that isn't skipped stops the whole run on the server, so Import skips them.
const rowsToSkip = computed(() => {
	const skipped = new Set(doc.value.skipped_rows.map((row) => Number(row.row_number)));
	const shown = previewReady.value ? preview.value : null;
	return errorRowNumbers(doc.value, shown).filter((row) => !skipped.has(row));
});

function skipErrorRowsAndImport() {
	skipRows(doc.value, previewReady.value ? preview.value : null, rowsToSkip.value);
	beginImport();
}

// Retry stays on the result until the run reports progress or the import reloads with
// its new result; on a developer site the run finishes inside the start request.
const retrying = ref(false);
// The saved import's `modified` when the run was asked for; null until then.
let retriedFrom: string | null = null;

async function retryImport() {
	retrying.value = true;
	if (!(await saveIfDirty())) return stopRetrying();
	retriedFrom = doc.value.modified ?? "";
	if (!(await props.dataImport.start({ waitForProgress: true }))) stopRetrying();
}

function stopRetrying() {
	retrying.value = false;
	retriedFrom = null;
}

watch([running, blocked, () => doc.value.modified], ([isRunning, isBlocked, modified]) => {
	if (retriedFrom === null) return;
	if (isRunning || isBlocked || (modified ?? "") !== retriedFrom) stopRetrying();
});

/** The run reads the saved import, so unsaved fixes are saved first. */
async function beginImport() {
	starting.value = true;
	try {
		if (!(await saveIfDirty())) return;
		current.value = IMPORT;
		await props.dataImport.start();
	} finally {
		starting.value = false;
	}
}

async function stopImport({ close }: { close: () => void }) {
	const response = await props.dataImport.stop();
	close();
	if (response?.status === "not_running")
		toast.warning(t("Job was not running; status updated."));
	else toast(t("Job Stopped Successfully"));
}
</script>
