<!--
  GroupBy — a controlled, meta-driven list-view control. Its `v-model` is a GroupBySettings
  (`{ fields, aggregates }`) or `null` for an ungrouped list; it owns no data resource.
  The host turns the model into a grouped query with `serializeGroupBy`, fetches the
  rows and shows them in `GroupByTable`.

  Edits stay in a local draft until Apply, the way desk's report view group by works,
  so a half-built grouping never refetches the list. Field Options come from Meta.
-->
<template>
	<Popover v-model:open="open" side="bottom" :align="align" :autoFocus="false">
		<template #trigger>
			<div class="flex items-center">
				<Button
					:icon="hideLabel ? 'lucide-folder' : undefined"
					:iconLeft="hideLabel ? undefined : 'lucide-folder'"
					:class="model ? 'rounded-r-none' : ''"
					:tooltip="model ? __('Grouped by {0}', [groupedLabels]) : undefined"
					:aria-label="__('Group')"
				>
					<span v-if="!hideLabel" class="block max-w-60 truncate">
						{{ model ? __("Grouped by {0}", [groupedLabels]) : __("Group") }}
					</span>
				</Button>
				<Button
					v-if="model"
					class="rounded-l-none border-l"
					icon="lucide-x"
					:aria-label="__('Clear grouping')"
					@click.stop="model = null"
				/>
			</div>
		</template>
		<template #default="{ close }">
			<div
				ref="panel"
				tabindex="-1"
				class="flex w-[min(26rem,calc(100vw-2rem))] flex-col gap-4 p-2 outline-none"
			>
				<div class="flex flex-col gap-2">
					<div class="text-p-sm text-ink-gray-5">{{ __("Group By") }}</div>
					<div
						v-for="(fieldname, i) in draft.fields"
						:key="i"
						class="flex items-center gap-2"
					>
						<Combobox
							class="flex-1"
							:modelValue="fieldname || null"
							:options="groupOptions(fieldname)"
							:placeholder="__('Select field')"
							@update:modelValue="(v: string) => (draft.fields[i] = v)"
						/>
						<Button
							icon="lucide-x"
							variant="ghost"
							:aria-label="__('Remove')"
							@click="draft.fields.splice(i, 1)"
						/>
					</div>
					<Button
						class="self-start"
						variant="ghost"
						iconLeft="lucide-plus"
						:label="__('Add Group By')"
						@click="draft.fields.push('')"
					/>
				</div>
				<div class="flex flex-col gap-2">
					<div class="text-p-sm text-ink-gray-5">{{ __("Aggregate") }}</div>
					<div
						v-for="(aggregate, i) in draft.aggregates"
						:key="i"
						class="flex items-center gap-2"
					>
						<Select
							class="w-32"
							:modelValue="aggregate.function"
							:options="functionOptions(i)"
							@update:modelValue="(fn: AggregateFunction) => setFunction(i, fn)"
						/>
						<Combobox
							v-if="aggregate.function !== 'count'"
							class="flex-1"
							:modelValue="aggregate.fieldname || null"
							:options="aggregateOptions(i, aggregate.function)"
							:placeholder="__('Select field')"
							@update:modelValue="(v: string) => (aggregate.fieldname = v)"
						/>
						<div v-else class="flex-1" />
						<Button
							icon="lucide-x"
							variant="ghost"
							:aria-label="__('Remove')"
							@click="draft.aggregates.splice(i, 1)"
						/>
					</div>
					<Button
						class="self-start"
						variant="ghost"
						iconLeft="lucide-plus"
						:label="__('Add Aggregate')"
						@click="addAggregate"
					/>
				</div>
				<div
					class="flex items-center justify-between gap-2 border-t border-outline-gray-1 pt-3"
				>
					<Switch v-model="draft.showTotals" :label="__('Show totals')" />
					<div class="flex gap-2">
						<Button :label="__('Clear Grouping')" @click="clear(close)" />
						<Button
							variant="solid"
							:label="__('Apply')"
							:disabled="!canApply"
							@click="apply(close)"
						/>
					</div>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { Button, Combobox, Popover, Select, Switch } from "frappe-ui";
import { computed, nextTick, ref, watch } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { translate as __ } from "../../utils/translate";
import {
	AGGREGATE_FUNCTIONS,
	findGroupByField,
	getAggregateFields,
	getGroupByFields,
	isAggregateTaken,
	isCompleteAggregate,
} from "./groupBy";
import type {
	AggregateDraft,
	AggregateFunction,
	GroupByField,
	GroupByProps,
	GroupBySettings,
} from "./types";

const props = withDefaults(defineProps<GroupByProps>(), {
	hideLabel: false,
	align: "end",
});

const model = defineModel<GroupBySettings | null>({ default: null });

const { meta } = useDoctypeMeta(() => props.doctype);

const open = ref(false);
const panel = ref<HTMLElement | null>(null);
// The panel's working copy, whose rows can be blank until Apply drops them.
interface GroupByDraft {
	fields: string[];
	aggregates: AggregateDraft[];
	showTotals?: boolean;
}

const draft = ref<GroupByDraft>(emptyDraft());

function emptyDraft(): GroupByDraft {
	return { fields: [""], aggregates: [{ function: "count" }] };
}

// Reopening starts from the applied grouping, so closing without Apply discards edits.
// Focus lands on the panel, not the first field, which would select its text.
watch(open, async (isOpen) => {
	if (!isOpen) return;
	draft.value = model.value ? copy(model.value) : emptyDraft();
	await nextTick();
	panel.value?.focus({ preventScroll: true });
});

const metaFields = computed(() => meta.value?.fields ?? []);

// Pickers list fields alphabetically, as desk's report view does.
const toOptions = (fields: GroupByField[]) =>
	fields
		.map((f) => ({ label: __(f.label), value: f.fieldname }))
		.sort((a, b) => a.label.localeCompare(b.label));

const groupedLabels = computed(() =>
	(model.value?.fields ?? [])
		.map((f) => __(findGroupByField(metaFields.value, f)?.label ?? f))
		.join(", ")
);

// A field already grouped on isn't offered again, except in its own row.
function groupOptions(current: string) {
	return toOptions(
		getGroupByFields(metaFields.value).filter(
			(f) => f.fieldname === current || !draft.value.fields.includes(f.fieldname)
		)
	);
}

function isTaken(i: number, aggregate: AggregateDraft) {
	return isAggregateTaken(draft.value.aggregates, i, aggregate);
}

// An aggregate already added isn't offered again, except in its own row.
function functionOptions(i: number) {
	return AGGREGATE_FUNCTIONS.map((f) => ({
		label: __(f.label),
		value: f.value,
		disabled: f.value === "count" && isTaken(i, { function: "count" }),
	}));
}

function aggregateOptions(i: number, fn: AggregateFunction) {
	return toOptions(
		getAggregateFields(metaFields.value, fn).filter(
			(f) => !isTaken(i, { function: fn, fieldname: f.fieldname })
		)
	);
}

// A new row starts as Count, or as a Sum with no field yet once there's a Count.
function addAggregate() {
	const hasCount = isTaken(-1, { function: "count" });
	draft.value.aggregates.push({ function: hasCount ? "sum" : "count" });
}

// Switching function keeps the field only when the new function can still use it.
function setFunction(i: number, fn: AggregateFunction) {
	const aggregate = draft.value.aggregates[i];
	const keepsField = aggregateOptions(i, fn).some((o) => o.value === aggregate.fieldname);
	draft.value.aggregates[i] = keepsField ? { ...aggregate, function: fn } : { function: fn };
}

const canApply = computed(() => draft.value.fields.some(Boolean));

// The draft is reactive, so hand the model a plain copy the host can clone or store.
function apply(close: () => void) {
	// Dragged widths and the header sort carry over; one for a column that's gone is unused.
	model.value = copy({
		fields: draft.value.fields.filter(Boolean),
		aggregates: draft.value.aggregates.filter(isCompleteAggregate),
		widths: model.value?.widths,
		sort: model.value?.sort,
		showTotals: draft.value.showTotals || undefined,
	});
	close();
}

function copy(groupBy: GroupBySettings): GroupBySettings {
	const copied: GroupBySettings = {
		fields: [...groupBy.fields],
		aggregates: groupBy.aggregates.map((a) => ({ ...a })),
	};
	if (groupBy.widths) copied.widths = { ...groupBy.widths };
	if (groupBy.sort) copied.sort = groupBy.sort.map((sort) => ({ ...sort }));
	if (groupBy.showTotals) copied.showTotals = true;
	return copied;
}

function clear(close: () => void) {
	model.value = null;
	close();
}
</script>
