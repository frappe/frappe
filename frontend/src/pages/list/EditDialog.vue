<!-- The bulk Edit: pick fields, give each a value, and set them on every selected record in one run. -->
<template>
	<Dialog v-model="open" :title="title" size="lg" :actions="actions">
		<template #default>
			<p v-if="loading" class="text-sm text-ink-gray-5">{{ __("Loading fields…") }}</p>
			<div v-else class="flex flex-col gap-3">
				<div v-for="(row, index) in rows" :key="row.id" class="flex items-start gap-2">
					<div class="edit-picker w-48 shrink-0">
						<Select
							class="w-full"
							:aria-label="__('Field')"
							:modelValue="row.key"
							:options="optionsFor(row.key)"
							@update:modelValue="(key: string) => pick(row, key)"
						/>
					</div>
					<div class="edit-value flex min-h-7 min-w-0 flex-1 flex-col justify-center">
						<FormLayout
							v-if="row.key"
							:key="row.key"
							v-model:doc="row.doc"
							:layout="layoutOf(row)"
							:doctype="fieldOf(row.key)!.doctype"
						/>
					</div>
					<Button
						class="shrink-0"
						variant="ghost"
						icon="lucide-x"
						:aria-label="__('Remove field')"
						:disabled="rows.length === 1"
						@click="rows.splice(index, 1)"
					/>
				</div>
				<div>
					<Button
						variant="ghost"
						icon-left="lucide-plus"
						:label="__('Add field')"
						@click="add"
					/>
				</div>
				<p v-if="failure" class="whitespace-pre-line text-sm text-ink-red-4">
					{{ failure }}
				</p>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { getMeta } from "@framework/ui/api";
import { FormLayout, fieldsToLayout, mapField, type RawMetaField } from "@framework/ui/FormLayout";
import { CommitKey, NO_COMMIT } from "@framework/ui/FormLayout/types";
import { Button, Dialog, Select, toast } from "frappe-ui";
import { computed, provide, ref, watch } from "vue";
import { __, __n } from "@/i18n";
import { editableFields, updateFrom, type EditOutcome, type EditableField } from "@/list/bulkEdit";
import type { BulkUpdate } from "@framework/ui/api";

const props = defineProps<{
	doctype: string;
	count: number;
	/** The run takes every record the filters show. */
	all?: boolean;
	/** The count is a floor, shown with a "+". */
	approx?: boolean;
	run: (update: BulkUpdate) => Promise<EditOutcome>;
	/** Follows a background run in the shell. */
	follow: (taskId: string) => void;
}>();
const open = defineModel<boolean>({ default: false });

interface EditRow {
	id: number;
	key: string;
	doc: Record<string, unknown>;
}

const fields = ref<EditableField[]>([]);
const loading = ref(true);
// The dialog has no record to commit to.
provide(CommitKey, NO_COMMIT);
const rows = ref<EditRow[]>([]);
const saving = ref(false);
const failure = ref("");
const asked = ref({ count: 0, all: false, approx: false });
let ids = 0;
const newRow = (): EditRow => ({ id: ++ids, key: "", doc: {} });

watch(
	open,
	(isOpen) => {
		failure.value = "";
		if (!isOpen) return;
		if (!fields.value.length && !loading.value) {
			loading.value = true;
			load();
		}
		asked.value = { count: props.count, all: !!props.all, approx: !!props.approx };
		rows.value = [newRow()];
	},
	{ immediate: true }
);

load();
async function load() {
	try {
		const { data, children } = await getMeta<{ fields: RawMetaField[] }>(props.doctype, {
			include: "children",
		});
		const byChild = Object.fromEntries(
			Object.entries((children ?? {}) as Record<string, { fields: RawMetaField[] }>).map(
				([name, meta]) => [name, meta.fields]
			)
		);
		fields.value = editableFields(props.doctype, data.fields, byChild);
	} catch (error) {
		failure.value = error instanceof Error ? error.message : String(error);
	} finally {
		loading.value = false;
	}
}

const fieldOf = (key: string) => fields.value.find((one) => one.key === key);
const add = () => rows.value.push(newRow());

const taken = computed(() => new Set(rows.value.map((row) => row.key)));
const optionsFor = (current: string) =>
	fields.value
		.filter((one) => one.key === current || !taken.value.has(one.key))
		.map((one) => ({ label: one.label, value: one.key }));

function pick(row: EditRow, key: string) {
	row.key = key;
	row.doc = {};
}

function layoutOf(row: EditRow) {
	const one = fieldOf(row.key)!;
	// One bare control per row: no label or description line, and no condition that hides or locks it.
	const bare = {
		...one.field,
		label: "",
		placeholder: one.label,
		description: undefined,
		reqd: 0,
		read_only: 0,
		hidden: 0,
		depends_on: undefined,
		mandatory_depends_on: undefined,
		read_only_depends_on: undefined,
	};
	return fieldsToLayout([mapField(bare, {})]);
}

const scope = computed(() => {
	const { count, all, approx } = asked.value;
	const shown = count.toLocaleString() + (approx ? "+" : "");
	return all
		? __("all {0} matching records", [shown])
		: __n("{0} selected record", "{0} selected records", count, [shown]);
});
const title = computed(() => __("Edit {0}", [scope.value]));

const picked = computed(() =>
	rows.value.flatMap((row) => {
		const field = fieldOf(row.key);
		return field ? [{ field, value: row.doc[field.field.fieldname] }] : [];
	})
);

const actions = computed(() =>
	failure.value && !loading.value && !picked.value.length
		? [{ label: __("Close"), onClick: () => (open.value = false) }]
		: [
				{
					label: __("Update"),
					variant: "solid",
					loading: saving.value,
					disabled: !picked.value.length,
					onClick: confirm,
				},
		  ]
);

async function confirm() {
	saving.value = true;
	failure.value = "";
	try {
		report(await props.run(updateFrom(picked.value)));
	} catch (error) {
		failure.value = error instanceof Error ? error.message : String(error);
	} finally {
		saving.value = false;
	}
}

function report(outcome: EditOutcome) {
	if (outcome.queued) {
		toast.info(__("Updating in the background"));
		props.follow(outcome.queued.task_id);
	}
	if (outcome.updated.length)
		toast.success(
			__n("Updated {0} record", "Updated {0} records", outcome.updated.length, [
				outcome.updated.length,
			])
		);
	if (!outcome.failed.length) {
		open.value = false;
		return;
	}
	failure.value = outcome.failed.map(({ name, error }) => `${name}: ${error}`).join("\n");
}
</script>

<style scoped>
/* The picker fills a fixed column: frappe-ui's widest-option sizer would push a long label past its ellipsis. */
.edit-picker :deep(.select-trigger-sizer) {
	display: none;
}
/* A control without a label is drawn bare and inline: the field stretches it to the column. */
.edit-value :deep(.field) {
	display: flex;
	flex-direction: column;
}
/* The checkbox's 1px nudge lines it up with a label it no longer has. */
.edit-value :deep(input[type="checkbox"]) {
	margin-top: 0;
}
/* Link and Date draw a darker chevron than Select: every row takes the picker's. */
.edit-value :deep(.lucide-chevron-down) {
	color: var(--ink-gray-4);
}
</style>
