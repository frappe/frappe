<!--
  GroupBy — a controlled, meta-driven list-view control. Its `v-model` is a GroupBySettings
  (`{ fields, aggregates }`) or `null` for an ungrouped list; it owns no data resource.
  The host turns the model into a grouped query with `serializeGroupBy`, fetches the
  rows and shows them in `GroupByTable`.

  Edits stay in a local draft until Apply, the way desk's report view group by works,
  so a half-built grouping never refetches the list. Field Options come from Meta.
-->
<template>
	<Popover v-model:open="open" side="bottom" :align="align">
		<template #trigger>
			<div class="flex items-center">
				<Button
					:label="hideLabel ? undefined : model ? 'Grouped' : 'Group'"
					:icon="hideLabel ? 'lucide-folder' : undefined"
					:iconLeft="hideLabel ? undefined : 'lucide-folder'"
					:class="model ? 'rounded-r-none' : ''"
					aria-label="Group"
				>
					<template v-if="model && !hideLabel" #suffix>
						<div
							class="flex h-5 w-5 items-center justify-center rounded-[5px] bg-surface-base pt-px text-xs-medium text-ink-gray-8 shadow-sm"
						>
							{{ model.fields.length }}
						</div>
					</template>
				</Button>
				<Button
					v-if="model"
					class="rounded-l-none border-l"
					icon="lucide-x"
					aria-label="Clear grouping"
					@click.stop="model = null"
				/>
			</div>
		</template>
		<template #default="{ close }">
			<div class="flex w-[26rem] flex-col gap-4 p-2">
				<div class="flex flex-col gap-2">
					<div class="text-p-sm text-ink-gray-5">Group By</div>
					<div
						v-for="(fieldname, i) in draft.fields"
						:key="i"
						class="flex items-center gap-2"
					>
						<Combobox
							class="flex-1"
							:modelValue="fieldname || null"
							:options="groupOptions(fieldname)"
							placeholder="Select field"
							@update:modelValue="(v: string) => (draft.fields[i] = v)"
						/>
						<Button
							icon="lucide-x"
							variant="ghost"
							aria-label="Remove"
							@click="draft.fields.splice(i, 1)"
						/>
					</div>
					<Button
						class="self-start"
						variant="ghost"
						iconLeft="lucide-plus"
						label="Add Group By"
						@click="draft.fields.push('')"
					/>
				</div>
				<div class="flex flex-col gap-2">
					<div class="text-p-sm text-ink-gray-5">Aggregate</div>
					<div
						v-for="(aggregate, i) in draft.aggregates"
						:key="i"
						class="flex items-center gap-2"
					>
						<Select
							class="w-32"
							:modelValue="aggregate.function"
							:options="functionOptions"
							@update:modelValue="(fn: AggregateFunction) => setFunction(i, fn)"
						/>
						<Combobox
							v-if="aggregate.function !== 'count'"
							class="flex-1"
							:modelValue="aggregate.fieldname || null"
							:options="aggregateOptions(aggregate.function)"
							placeholder="Select field"
							@update:modelValue="(v: string) => (aggregate.fieldname = v)"
						/>
						<div v-else class="flex-1" />
						<Button
							icon="lucide-x"
							variant="ghost"
							aria-label="Remove"
							@click="draft.aggregates.splice(i, 1)"
						/>
					</div>
					<Button
						class="self-start"
						variant="ghost"
						iconLeft="lucide-plus"
						label="Add Aggregate"
						@click="draft.aggregates.push({ function: 'count' })"
					/>
				</div>
				<div class="flex justify-end gap-2 border-t border-outline-gray-1 pt-3">
					<Button label="Clear Grouping" @click="clear(close)" />
					<Button
						variant="solid"
						label="Apply"
						:disabled="!canApply"
						@click="apply(close)"
					/>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { Button, Combobox, Popover, Select } from "frappe-ui";
import { computed, ref, toRaw, watch } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import {
	AGGREGATE_FUNCTIONS,
	getAggregateFields,
	getGroupByFields,
	isCompleteAggregate,
} from "./groupBy";
import type { AggregateFunction, GroupByField, GroupByProps, GroupBySettings } from "./types";

const props = withDefaults(defineProps<GroupByProps>(), {
	hideLabel: false,
	align: "end",
});

const model = defineModel<GroupBySettings | null>({ default: null });

const { meta } = useDoctypeMeta(() => props.doctype);

const open = ref(false);
const draft = ref<GroupBySettings>(emptyDraft());

function emptyDraft(): GroupBySettings {
	return { fields: [""], aggregates: [{ function: "count" }] };
}

// Reopening starts from the applied grouping, so closing without Apply discards edits.
watch(open, (isOpen) => {
	if (!isOpen) return;
	draft.value = model.value ? structuredClone(toRaw(model.value)) : emptyDraft();
});

const metaFields = computed(() => meta.value?.fields ?? []);

const functionOptions = AGGREGATE_FUNCTIONS.map((f) => ({ label: f.label, value: f.value }));

const toOption = (f: GroupByField) => ({ label: f.label, value: f.fieldname });

// A field already grouped on isn't offered again, except in its own row.
function groupOptions(current: string) {
	return getGroupByFields(metaFields.value)
		.filter((f) => f.fieldname === current || !draft.value.fields.includes(f.fieldname))
		.map(toOption);
}

function aggregateOptions(fn: AggregateFunction) {
	return getAggregateFields(metaFields.value, fn).map(toOption);
}

// Switching function keeps the field only when the new function can still use it.
function setFunction(i: number, fn: AggregateFunction) {
	const aggregate = draft.value.aggregates[i];
	const keepsField = aggregateOptions(fn).some((o) => o.value === aggregate.fieldname);
	draft.value.aggregates[i] = keepsField ? { ...aggregate, function: fn } : { function: fn };
}

const canApply = computed(() => draft.value.fields.some(Boolean));

function apply(close: () => void) {
	model.value = {
		fields: draft.value.fields.filter(Boolean),
		aggregates: draft.value.aggregates.filter(isCompleteAggregate),
	};
	close();
}

function clear(close: () => void) {
	model.value = null;
	close();
}
</script>
