<!-- The rule popover's content: Rules (ui's ConditionBuilder: AND/OR groups for a condition, a flat
     AND list for a Link's filters) or Code, which keeps a rule the builder cannot read as written. -->
<template>
	<div class="flex min-w-0 flex-col" data-rule-editor>
		<div class="flex items-center gap-2 px-4 pb-1 pt-3">
			<span class="shrink-0 truncate text-base font-medium text-ink-gray-8">{{
				title
			}}</span>
			<span class="min-w-0 truncate text-base text-ink-gray-5">{{ subject }}</span>
			<Tooltip
				:text="__('The rules cannot show this code. Edit it until they can, or clear it.')"
				:disabled="draft.readable.value"
			>
				<div class="ml-auto shrink-0">
					<TabButtons
						:options="modes"
						:model-value="draft.mode.value"
						data-rule-mode
						@update:model-value="draft.switchTo($event as RuleMode)"
					/>
				</div>
			</Tooltip>
		</div>
		<div class="px-4 py-3">
			<ConditionBuilder
				v-if="draft.mode.value === 'rules'"
				:model-value="draft.tree.value"
				:fields="fields"
				:max-depth="filters ? 0 : 3"
				bordered="all"
				class="rule-editor-builder"
				:labels="labels"
				:error="draft.problem.value"
				@update:model-value="draft.setTree($event)"
			>
				<template #empty>
					<span class="flex flex-col items-start gap-3 text-left">
						<span class="text-p-base text-ink-gray-5">{{ note }}</span>
						<span
							class="inline-flex h-7 items-center gap-1.5 rounded-4 bg-surface-gray-2 px-2 text-base text-ink-gray-8 hover:bg-surface-gray-3"
						>
							<span class="lucide-plus size-4" aria-hidden="true" />
							{{ labels.addCondition }}
						</span>
					</span>
				</template>
				<template #condition-value="cell">
					<RuleValue v-bind="cell" :referable="referable" :same-record="!filters" />
				</template>
				<!-- link_filters has no OR: every row joins by "and", as text. -->
				<template v-if="filters" #condition-conjunction>
					<span class="text-p-base text-ink-gray-6">{{ __("and") }}</span>
				</template>
				<!-- With no groups the builder's menu is a red trash; a gray × keeps the accents gray. -->
				<template v-if="filters" #condition-actions="{ remove }">
					<Tooltip :text="__('Remove filter')">
						<Button
							variant="ghost"
							icon="lucide-x"
							:label="__('Remove filter')"
							@click="remove"
						/>
					</Tooltip>
				</template>
			</ConditionBuilder>
			<template v-else>
				<Textarea
					variant="outline"
					:rows="filters ? 5 : 3"
					class="font-mono"
					:model-value="draft.code.value"
					:placeholder="filters ? FILTERS_EXAMPLE : 'doc.status === &quot;Open&quot;'"
					data-rule-code
					@update:model-value="draft.setCode(String($event ?? ''))"
				/>
				<p class="mt-2 flex items-start gap-1.5 text-p-sm text-ink-gray-5">
					<span class="lucide-info mt-px size-3.5 shrink-0" aria-hidden="true" />
					<span>{{ codeNote }}</span>
				</p>
			</template>
		</div>
		<div class="flex items-center gap-2 border-t border-outline-gray-1 px-4 py-2.5">
			<Button
				class="ml-auto"
				variant="ghost"
				:label="filters ? __('Clear filters') : __('Clear condition')"
				:disabled="!draft.value.value"
				data-rule-clear
				@click="draft.clear()"
			/>
			<Button variant="subtle" :label="__('Done')" data-rule-done @click="$emit('done')" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, TabButtons, Textarea, Tooltip } from "frappe-ui";
import { ConditionBuilder, type ConditionField } from "@framework/ui/ConditionBuilder";
import { __ } from "@/i18n";
import type { RuleDraft, RuleMode } from "./ruleDraft";
import RuleValue from "./RuleValue.vue";

const props = defineProps<{
	draft: RuleDraft;
	title: string;
	subject: string;
	/** Under the empty builder. */
	note: string;
	/** The fields a row names: this DocType's for a condition, the target's for filters. */
	fields: ConditionField[];
	/** The fields of this record a value may name. */
	referable: ConditionField[];
	filters?: boolean;
}>();
defineEmits<{ done: [] }>();

const FILTERS_EXAMPLE = '[["Customer", "disabled", "=", 0]]';

const modes = computed(() => [
	{ label: __("Rules"), value: "rules", disabled: !props.draft.readable.value },
	{ label: __("Code"), value: "code" },
]);
const labels = computed(() => ({
	addCondition: props.filters ? __("Add filter") : __("Add condition"),
	empty: props.note,
}));
const codeNote = computed(() => {
	const { draft, filters } = props;
	if (!draft.readable.value && draft.code.value.trim()) {
		return filters
			? __("The rules can't show these filters. They stay as code, as written.")
			: __("The rules can't show this condition. It stays as code, as written.");
	}
	return filters
		? __(
				"A JSON list of [DocType, field, operator, value]. A value eval:doc.company reads this record."
		  )
		: __("JavaScript. doc is the record.");
});
</script>

<style>
/* The popover is the card; the builder's root card would be a card in a card. */
.rule-editor-builder > div.rounded-6,
.rule-editor-builder [data-slot="condition-empty"] {
	border-width: 0;
	padding: 0;
}
.rule-editor-builder [data-slot="condition-empty"] {
	justify-content: flex-start;
}
</style>
