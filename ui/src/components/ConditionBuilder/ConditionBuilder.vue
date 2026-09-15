<!--
  ConditionBuilder, a controlled editor for a nested and/or condition tree. Its
  `v-model` is the tree; it owns no data resource and never calls an app endpoint
  (FP2). The built-in leaf's fields come from the doctype's Meta (FP3) or from an
  explicit `fields` array. It owns the two singular things: the live region and
  focus.
-->
<template>
	<div ref="rootRef" data-slot="condition-builder" class="w-full">
		<div
			v-if="label"
			:id="labelId"
			data-slot="condition-label"
			class="mb-1.5 text-p-sm text-ink-gray-5"
		>
			{{ label }}
			<span v-if="required" aria-hidden="true" class="text-ink-red-6">*</span>
			<span v-if="required" class="sr-only">(required)</span>
		</div>

		<div
			v-if="description"
			:id="descriptionId"
			data-slot="condition-description"
			class="mb-2 text-p-sm text-ink-gray-5"
		>
			{{ description }}
		</div>

		<div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
			{{ announcement }}
		</div>

		<div
			v-if="fieldsError"
			data-slot="condition-fields-error"
			class="mb-4 flex items-center gap-2 rounded-md bg-surface-red-2 p-2 text-p-sm text-ink-red-6"
		>
			<span :id="fieldsErrorId" class="min-w-0 flex-1">{{ labels.fieldsError }}</span>
			<Button
				:label="labels.retryFields"
				:aria-labelledby="`${retryId} ${fieldsErrorId}`"
				@click="reloadFields"
			/>
			<span :id="retryId" class="sr-only">{{ labels.retryFields }}</span>
		</div>

		<!-- One element, not a button and a div: only the tag and the click differ,
		and the fallback content was written twice. A read-only empty state still
		takes focus, through tabindex, without claiming to be a button. -->
		<component
			:is="readonly ? 'div' : 'button'"
			v-if="isEmpty"
			data-slot="condition-empty"
			:type="readonly ? undefined : 'button'"
			:tabindex="readonly ? -1 : undefined"
			class="flex w-full items-center justify-center gap-2 rounded-md border border-outline-gray-2 p-4 text-p-sm text-ink-gray-5"
			:class="!readonly && 'cursor-pointer'"
			@click="onEmptyClick"
		>
			<slot name="empty">
				<span class="lucide-plus size-4" aria-hidden="true" />
				{{ labels.empty }}
			</slot>
		</component>

		<div
			v-else
			class="flex w-full flex-col gap-4"
			:class="bordered !== 'none' && 'rounded-lg border border-outline-gray-2 p-3'"
		>
			<ConditionGroup :group="tree" :path="[]">
				<template v-if="$slots.condition" #condition="slotProps">
					<slot name="condition" v-bind="asConditionSlotProps(slotProps)" />
				</template>
				<template v-if="$slots.group" #group="groupSlot">
					<slot name="group" v-bind="asGroupSlotProps(groupSlot)" />
				</template>
				<template v-if="$slots['condition-value']" #condition-value="valueProps">
					<slot name="condition-value" v-bind="valueProps" />
				</template>
				<template v-if="$slots['condition-where']" #condition-where="whereSlot">
					<slot name="condition-where" v-bind="whereSlot" />
				</template>
				<template v-if="$slots['condition-conjunction']" #condition-conjunction="conjSlot">
					<slot name="condition-conjunction" v-bind="conjSlot" />
				</template>
				<template v-if="$slots['condition-actions']" #condition-actions="actionsSlot">
					<slot name="condition-actions" v-bind="actionsSlot" />
				</template>
				<template v-if="$slots['add-condition']" #add-condition="addSlot">
					<slot name="add-condition" v-bind="addSlot" />
				</template>
			</ConditionGroup>
		</div>

		<div
			v-if="errorText"
			:id="errorId"
			data-slot="condition-error"
			class="mt-2 text-p-sm text-ink-red-6"
		>
			{{ errorText }}
		</div>
	</div>
</template>

<script setup lang="ts" generic="TLeaf = FieldConditionValue">
import { computed, nextTick, provide, ref, useId, watch } from "vue";
import { Button } from "frappe-ui";
import ConditionGroup from "./ConditionGroup.vue";
import { useConditionFields } from "./internal/fields";
import {
	focusAfterAdd,
	focusAfterAddGroup,
	focusAfterRemove,
	useConditionFocus,
} from "./internal/focus";
import {
	conditionBuilderKey,
	DEFAULT_BORDERS,
	DEFAULT_MAX_DEPTH,
	DEFAULT_REORDERABLE,
	mergeColumns,
	mergeLabels,
	uncachedLabels,
} from "./internal/context";
import {
	addCondition as addConditionAt,
	addGroup as addGroupAt,
	canMoveInto,
	countConditions,
	countGroups,
	emptyTree,
	getNode,
	isGroup,
	moveNode,
	removeNode,
	samePath,
	setGroupConjunction,
	turnIntoGroup as turnIntoGroupAt,
	ungroup as ungroupAt,
	updateLeaf,
} from "./tree";
import type {
	ConditionBuilderProps,
	ConditionBuilderSlots,
	ConditionField,
	ConditionGroup as ConditionGroupType,
	ConditionPath,
	ConditionSlotProps,
	Conjunction,
	FieldConditionValue,
	GroupSlotProps,
} from "./types";

// Declared explicitly: the slots are forwarded down the tree, not rendered
// here, so vue-component-meta cannot infer them.
defineSlots<ConditionBuilderSlots<TLeaf>>();

// ConditionGroup types its slots as `unknown` to break a recursive inference
// cycle, so re-forwarding needs a cast back.
function asConditionSlotProps(slotProps: ConditionSlotProps<unknown>): ConditionSlotProps<TLeaf> {
	return slotProps as ConditionSlotProps<TLeaf>;
}

function asGroupSlotProps(slotProps: GroupSlotProps<unknown>): GroupSlotProps<TLeaf> {
	return slotProps as GroupSlotProps<TLeaf>;
}

const props = withDefaults(defineProps<ConditionBuilderProps<TLeaf>>(), {
	maxDepth: DEFAULT_MAX_DEPTH,
	bordered: DEFAULT_BORDERS,
	readonly: false,
	reorderable: DEFAULT_REORDERABLE,
});

const emit = defineEmits<{
	"update:modelValue": [value: ConditionGroupType<TLeaf>];
	"update:expression": [value: string];
}>();

const rootRef = ref<HTMLElement | null>(null);
const id = useId();
const fieldsErrorId = useId();
const labelId = useId();
const descriptionId = useId();
const errorId = useId();

// `error` takes a string or an Error, per the shared contract.
const errorText = computed(() =>
	props.error instanceof Error ? props.error.message : props.error
);
const retryId = useId();

// The row a drag is carrying, for as long as it is carrying it. Lives here so
// every group sees the same one; see `dragFrom` on the context.
const dragFrom = ref<ConditionPath | null>(null);

const { moveFocus, focusAfterMenuCloses } = useConditionFocus(id, rootRef);

// Controlled outright. A host that drops the event renders a tree that does not
// move.
const tree = computed<ConditionGroupType<TLeaf>>(() => props.modelValue ?? emptyTree<TLeaf>());

// See `uncachedLabels`: a `computed` would freeze the labels in whatever
// language was current at first render.
const labels = uncachedLabels(() => mergeLabels(props.labels));
const columns = computed(() => mergeColumns(props.columns));
const isEmpty = computed(() => tree.value.conditions.length === 0);

const { fields, fieldsLoading, fieldsError, reloadFields } = useConditionFields(
	props,
	tree,
	(value) => emit("update:expression", value)
);

const announcement = ref("");
let pending: string[] = [];

// Cleared first so the same message twice is still a change; messages in one
// tick are joined.
function announce(message: string) {
	pending.push(message);
	announcement.value = "";
	nextTick(() => {
		if (pending.length === 0) return;
		announcement.value = pending.join(" ");
		pending = [];
	});
}

// Announced so a second failure after a retry is announced too.
watch(fieldsError, (error) => {
	if (error) announce(labels.value.fieldsError);
});

function newLeaf(): TLeaf {
	if (props.newCondition) return props.newCondition();
	return { fieldname: "", operator: "equals", value: "" } as TLeaf;
}

function commit(next: ConditionGroupType<TLeaf>) {
	emit("update:modelValue", next);
}

function onEmptyClick() {
	if (!props.readonly) addCondition([]);
}

/** Append a condition to the group at `path` and put focus in it. */
function addCondition(path: ConditionPath) {
	const next = addConditionAt(tree.value, path, newLeaf());
	commit(next);
	moveFocus(focusAfterAdd(next, path), "add");
}

provide(conditionBuilderKey, {
	builderId: computed(() => id),
	labelId: computed(() => (props.label ? labelId : "")),
	// Both, in reading order, so a screen reader gets the description before the
	// error rather than in id order.
	describedBy: computed(() =>
		[props.description ? descriptionId : "", errorText.value ? errorId : ""]
			.filter(Boolean)
			.join(" ")
	),
	invalid: computed(() => Boolean(errorText.value)),
	fields,
	fieldsLoading,
	fieldsError,
	reloadFields,
	columns,
	labels,
	bordered: computed(() => props.bordered),
	maxDepth: computed(() => props.maxDepth),
	readonly: computed(() => props.readonly),
	reorderable: computed(() => props.reorderable),

	addCondition,
	addGroup: (path: ConditionPath) => {
		const next = addGroupAt(tree.value, path, newLeaf());
		commit(next);
		moveFocus(focusAfterAddGroup(next, path), "add");
	},
	remove: (path: ConditionPath) => {
		const removed = getNode(tree.value, path);
		const groupsBefore = countGroups(tree.value);
		const next = removeNode(tree.value, path);
		commit(next);
		// Only a removed condition counts: removing a group is meant to take
		// one.
		const cascaded =
			removed !== undefined && !isGroup(removed) && countGroups(next) < groupsBefore;
		announce(labels.value.removed(countConditions(next), cascaded));
		moveFocus(focusAfterRemove(next, path), "remove");
	},
	update: (path: ConditionPath, leaf: unknown) =>
		commit(updateLeaf(tree.value, path, leaf as TLeaf)),
	turnIntoGroup: (path: ConditionPath) => commit(turnIntoGroupAt(tree.value, path)),
	// The group's row goes with the menu, so focus lands as a removal places
	// it.
	ungroup: (path: ConditionPath) => {
		const next = ungroupAt(tree.value, path);
		commit(next);
		moveFocus(focusAfterRemove(next, path), "remove");
	},
	setConjunction: (path: ConditionPath, value: Conjunction) =>
		commit(setGroupConjunction(tree.value, path, value)),
	// A reorder keeps every path valid: only the two swapped rows change.
	move: (
		path: ConditionPath,
		from: number,
		to: number,
		options?: { name?: string; focus?: boolean }
	) => {
		const group = getNode(tree.value, path);
		if (group === undefined || !isGroup(group)) return;
		const total = group.conditions.length;
		if (from === to || from < 0 || to < 0 || from >= total || to >= total) return;

		commit(moveNode(tree.value, [...path, from], path, to, props.maxDepth));
		announce(labels.value.moved(options?.name ?? "", from + 1, to + 1, total));
		// Onto the row's menu at its new position, outlasting the menu it ran
		// from, which restores focus to the row this one displaced.
		if (options?.focus !== false) focusAfterMenuCloses([...path, to]);
	},
	canDrop: (from: ConditionPath, toGroupPath: ConditionPath) =>
		canMoveInto(tree.value, from, toGroupPath, props.maxDepth),
	dragFrom,
	// Counts are read before the edit, which re-points the paths.
	moveInto: (
		from: ConditionPath,
		toGroupPath: ConditionPath,
		toIndex: number,
		options?: { name?: string }
	) => {
		if (!canMoveInto(tree.value, from, toGroupPath, props.maxDepth)) return;

		const target = getNode(tree.value, toGroupPath);
		if (target === undefined || !isGroup(target)) return;

		const sameGroup = samePath(from.slice(0, -1), toGroupPath);
		const total = target.conditions.length + (sameGroup ? 0 : 1);
		const name = options?.name ?? "";

		commit(moveNode(tree.value, from, toGroupPath, toIndex, props.maxDepth));

		// A reparent cannot name where it came from: that position is in a
		// group the row has left.
		announce(
			sameGroup
				? labels.value.moved(name, from[from.length - 1] + 1, toIndex + 1, total)
				: labels.value.movedToGroup(name, toIndex + 1, total)
		);
		// No focus is placed: the pointer took none.
	},
	announce,
});
</script>
