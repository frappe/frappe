<!--
  One group of conditions, rendering its children and itself again for a nested
  group. The root is a `<fieldset>` with a hidden `<legend>`; nested groups use
  `role="group"`. `role="list"` stays explicit: WebKit drops list semantics under
  `list-style: none`, taking the item count with it.
-->
<template>
	<component
		:is="rootTag"
		data-slot="condition-group"
		:data-depth="path.length"
		:role="rootTag === 'fieldset' ? undefined : 'group'"
		:aria-label="rootTag === 'fieldset' ? undefined : groupName"
		:aria-labelledby="labelledBy"
		:aria-describedby="describedBy || undefined"
		:aria-invalid="invalid || undefined"
		class="flex w-full min-w-0 flex-col gap-4"
		:class="hasCard && 'rounded-lg border border-outline-gray-2 bg-surface-white p-3'"
	>
		<legend v-if="rootTag === 'fieldset'" :id="legendId" class="sr-only">
			{{ groupName }}
		</legend>

		<!-- Each row carries its own grid rather than sharing one with its
		siblings: a shared grid sizes every track from the widest cell in the
		group. What the rows do share is their end edge, so the actions line up.

		`ghost-class` marks the slot the row would land in; the fill marks every
		list that would take it, and a list left unfilled is one that refuses.

		Nothing may sit between this tag and its `#item` template: vuedraggable's
		`computeNodes` requires that slot to render exactly one node, and a comment
		counts as a second one. -->
		<Draggable
			v-if="group.conditions.length"
			:model-value="group.conditions"
			:item-key="keyOf"
			:disabled="!canReorder"
			:group="sortableGroup"
			handle=".condition-drag-handle"
			tag="ul"
			role="list"
			:data-group-path="path.join('.')"
			:data-condition-builder="builderId"
			class="flex w-full min-w-0 list-none flex-col gap-4 rounded-md"
			:class="canTakeDrag && 'bg-surface-gray-2'"
			ghost-class="opacity-40"
			chosen-class="cursor-grabbing"
			@start="onDragStart"
			@end="onDragEnd"
		>
			<template #item="{ element: condition, index }">
				<li
					class="group/row grid min-w-0 items-start gap-x-2"
					:style="{ gridTemplateColumns: trackListFor(condition) }"
					:data-condition-path="[...path, index].join('.')"
					:data-condition-builder="builderId"
				>
					<!-- The row owns the leading cell, not what goes in it. The band
					is one control tall and centres its content, so a bare word lines
					up with the controls beside it instead of sitting above them, and
					it grows if the host's cell is taller. The bracket is drawn here
					for the same reason: it spans the row, and replacing the cell
					should not erase it. -->
					<ConditionRule
						:index="index"
						:count="group.conditions.length"
						:offset="firstLineOffset(condition)"
					>
						<div
							class="flex min-h-7 items-center justify-center"
							:style="firstLineStyle(condition)"
						>
							<slot v-if="index === 0" name="condition-where" v-bind="whereProps()">
								<ConjunctionCell v-bind="cellProps(index)" />
							</slot>
							<slot
								v-else
								name="condition-conjunction"
								v-bind="conjunctionProps(index)"
							>
								<ConjunctionCell v-bind="cellProps(index)" />
							</slot>
						</div>
					</ConditionRule>

					<!-- Pointer-only, and hidden from assistive tech: it duplicates no
					control, so there is nothing for it to name. A keyboard path to
					the same edit goes in `#condition-actions`. -->
					<div
						v-if="canReorder"
						class="condition-drag-handle flex h-7 w-5 cursor-grab items-center justify-center active:cursor-grabbing"
						:style="firstLineStyle(condition)"
						aria-hidden="true"
					>
						<span
							class="lucide-grip-vertical size-4 text-ink-gray-4 transition-colors motion-reduce:transition-none group-hover/row:text-ink-gray-6"
						/>
					</div>

					<!-- A card gets a row of its own shape: one stretching track, so
					it runs to the end of the row rather than to wherever three
					content-sized cells stop.

					`#group` wraps what goes in that cell and is handed the default
					rendering as a component, so a host can put the real group
					elsewhere, a dialog body most of all. The fallback renders that
					same component. The row around it is not the slot's: `#condition-where`,
					`#condition-conjunction` and `#condition-actions` replace those. -->
					<template v-if="isGroup(condition)">
						<div class="min-w-0">
							<slot name="group" v-bind="groupSlotProps(condition, index)">
								<component :is="groupRenderer(index)" />
							</slot>
						</div>
					</template>

					<ConditionRow
						v-else
						:condition="condition"
						:path="[...path, index]"
						:field-label-id="rowFieldId(index)"
					>
						<template v-if="$slots.condition" #condition="slotProps">
							<slot name="condition" v-bind="slotProps" />
						</template>
						<template v-if="$slots['condition-value']" #condition-value="valueProps">
							<slot name="condition-value" v-bind="valueProps" />
						</template>
					</ConditionRow>

					<!-- The same first-line band as the leading cell, so `#condition-actions` is
					level with the controls rather than with the top of a grown row. -->
					<div
						class="flex min-h-7 items-center justify-end justify-self-end"
						:style="firstLineStyle(condition)"
					>
						<slot
							name="condition-actions"
							v-bind="actionsProps(index, isGroup(condition))"
						>
							<ConditionActions
								:path="[...path, index]"
								:is-group="isGroup(condition)"
								:field-label-id="rowFieldId(index)"
							/>
						</slot>
					</div>

					<span :id="rowFieldId(index)" class="sr-only">
						{{ leafFieldLabel(condition) }}
					</span>
				</li>
			</template>
		</Draggable>

		<div
			v-if="!readonly"
			class="flex"
			:data-add-group="path.join('.')"
			:data-condition-builder="builderId"
		>
			<slot name="add-condition" v-bind="addConditionProps()">
				<AddConditionButton :path="path" :can-add-group="canAddGroup" />
			</slot>
		</div>
	</component>
</template>

<script setup lang="ts">
import { computed, defineComponent, getCurrentInstance, h, useId, useSlots } from "vue";
import type { Component, Slot } from "vue";
// @ts-ignore, vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import AddConditionButton from "./AddConditionButton.vue";
import ConditionActions from "./ConditionActions.vue";
import ConditionRow from "./ConditionRow.vue";
import ConditionRule from "./ConditionRule.vue";
import ConjunctionCell from "./ConjunctionCell.vue";
import { useConditionBuilderContext } from "./internal/context";
import { useDragBridge } from "./internal/dragBridge";
import { useConditionLayout } from "./internal/layout";
import { canNest, isGroup, samePath } from "./tree";
import type {
	ActionsSlotProps,
	AddConditionSlotProps,
	ConditionBuilderSlots,
	ConditionGroup as ConditionGroupType,
	ConditionPath,
	ConjunctionSlotProps,
	Conjunction,
	FieldConditionValue,
	GroupSlotProps,
	WhereSlotProps,
} from "./types";

defineOptions({ name: "ConditionGroup" });

const props = defineProps<{
	group: ConditionGroupType<unknown>;
	path: ConditionPath;
}>();

// Explicit slot types break the inference cycle self-recursion creates.
type GroupSlots = Omit<ConditionBuilderSlots<unknown>, "empty">;

defineSlots<GroupSlots>();

const context = useConditionBuilderContext();
const slots = useSlots();
const rowIdPrefix = useId();

const builderId = computed(() => context.builderId.value);
const readonly = computed(() => context.readonly.value);

const canAddGroup = computed(() => canNest(props.path, context.maxDepth.value));

/** Whether this group's rows can be dragged. A read-only tree cannot be edited at all. */
const canReorder = computed(() => context.reorderable.value && !readonly.value);

const { trackListFor, firstLineOffset, firstLineStyle } = useConditionLayout(
	context.columns,
	context.bordered,
	canReorder
);

const { sortableGroup, canTakeDrag, onDragStart, onDragEnd } = useDragBridge(
	context,
	computed(() => props.path),
	computed(() => props.group),
	leafFieldLabel
);

/**
 * Keyed by index, so a row's DOM and the focus inside it survive an edit.
 * Keying by identity would remount every row on every keystroke.
 */
function keyOf(node: unknown): number {
	return props.group.conditions.indexOf(node);
}

// Only nested groups draw a card; the root's border is the builder's.
const isNested = computed(() => props.path.length > 0);
const hasCard = computed(() => isNested.value && context.bordered.value === "all");

// A `<fieldset>` groups form controls, and a read-only tree has none.
const rootTag = computed(() => (!isNested.value && !readonly.value ? "fieldset" : "div"));

const legendId = useId();

// The host's label names the whole control, and the legend still says how this
// level joins. Both, in that order, so the name reads "Conditions, match all".
// Only the root carries them: a nested group is named by its own conjunction.
const labelledBy = computed(() => {
	if (isNested.value || !context.labelId.value) return undefined;
	return `${context.labelId.value} ${legendId}`;
});
const describedBy = computed(() => (isNested.value ? "" : context.describedBy.value));
const invalid = computed(() => !isNested.value && context.invalid.value);

/** The group's operator, which every row after the first shows. */
const conjunction = computed<Conjunction>(() => props.group.conjunction ?? "and");

// A group's conjunction is otherwise conveyed only by a button between rows.
const groupName = computed(() =>
	conjunction.value === "or" ? context.labels.value.matchAny : context.labels.value.matchAll
);

/**
 * Exactly one cell per group is live: row 1. The rest render as text, not
 * disabled buttons, which a screen reader skips in forms mode and which is
 * exempt from the contrast minimum.
 */
function canToggleAt(index: number): boolean {
	return index === 1 && !readonly.value;
}

/** Id of the span holding a row's field label, which names its controls. */
function rowFieldId(index: number): string {
	return `${rowIdPrefix}-${index}`;
}

/**
 * Every control in a row is named after it, so eight operator selects are told
 * apart. Duck-typed on `fieldname`, so a custom leaf is labelled too.
 */
function leafFieldLabel(node: unknown): string {
	const fields = context.fields.value;
	if (node === null || typeof node !== "object") return "";
	const fieldname = (node as Partial<FieldConditionValue>).fieldname;
	if (typeof fieldname !== "string" || fieldname === "") return "";
	return fields.find((f) => f.fieldname === fieldname)?.label ?? fieldname;
}

/** What the built-in cell needs, whichever of the two slots falls back to it. */
function cellProps(index: number): Omit<ConjunctionSlotProps, "toggle"> {
	return {
		index,
		conjunction: conjunction.value,
		canToggle: canToggleAt(index),
		groupPath: props.path,
	};
}

function whereProps(): WhereSlotProps {
	return { groupPath: props.path, conjunction: conjunction.value };
}

function conjunctionProps(index: number): ConjunctionSlotProps {
	return { ...cellProps(index), toggle: toggleConjunction };
}

function toggleConjunction() {
	context.setConjunction(props.path, conjunction.value === "and" ? "or" : "and");
}

function actionsProps(index: number, group: boolean): ActionsSlotProps {
	const path = [...props.path, index];
	const last = props.group.conditions.length - 1;
	return {
		path,
		isGroup: group,
		readonly: readonly.value,
		canGroup: !group && canNest(props.path, context.maxDepth.value),
		canMoveUp: canReorder.value && index > 0,
		canMoveDown: canReorder.value && index < last,
		moveUp: () => moveRow(index, index - 1),
		moveDown: () => moveRow(index, index + 1),
		turnIntoGroup: () => context.turnIntoGroup(path),
		ungroup: () => context.ungroup(path),
		remove: () => context.remove(path),
	};
}

/** A move run from a row's menu, which keeps its focus on the way. */
function moveRow(from: number, to: number) {
	context.move(props.path, from, to, {
		name: leafFieldLabel(props.group.conditions[from]),
	});
}

function addConditionProps(): AddConditionSlotProps {
	return {
		groupPath: props.path,
		addCondition: () => context.addCondition(props.path),
		addGroup: () => context.addGroup(props.path),
		canAddGroup: canAddGroup.value,
	};
}

// `v-if="isGroup(...)"` does not narrow the union for vue-tsc, hence the cast.
function asGroup(node: unknown) {
	return node as ConditionGroupType<unknown>;
}

/**
 * `group` is among them: a host wrapping one level expects the same at every
 * level below.
 */
const FORWARDED_SLOTS = [
	"condition",
	"condition-value",
	"condition-where",
	"condition-conjunction",
	"condition-actions",
	"add-condition",
	"group",
] as const;

/**
 * `getCurrentInstance().type`, not an import: the template's self-reference is
 * not in scope, and importing the SFC into itself is a cycle.
 */
const self = getCurrentInstance()?.type as Component;

/**
 * A component, not a vnode, so `<component :is>` instantiates it fresh wherever
 * the host renders it. Cached per row index: a renderer built during render
 * would remount the subtree on every keystroke.
 */
const renderers = new Map<number, Component>();

function groupRenderer(index: number): Component {
	const cached = renderers.get(index);
	if (cached) return cached;

	const renderer = defineComponent({
		name: "ConditionGroupDefault",
		// Read at render time, so the component survives an edit replacing the
		// node.
		setup: () => () => renderNestedGroup(index),
	});

	renderers.set(index, renderer);
	return renderer;
}

/** The nested group in row `index`, with this group's slots passed down it. */
function renderNestedGroup(index: number) {
	const node = props.group.conditions[index];
	if (!isGroup(node)) return null;

	const forwarded: Record<string, Slot> = {};
	for (const name of FORWARDED_SLOTS) {
		const slot = slots[name];
		if (slot) forwarded[name] = slot;
	}

	return h(self, { group: asGroup(node), path: [...props.path, index] }, forwarded);
}

function groupSlotProps(node: unknown, index: number): GroupSlotProps<unknown> {
	return {
		group: asGroup(node),
		path: [...props.path, index],
		// The root never reaches this slot, so depth here is 1 or more.
		depth: props.path.length + 1,
		readonly: readonly.value,
		Group: groupRenderer(index),
	};
}
</script>
