<!--
	Root of the advanced filter builder. Owns the filter tree, seeded either from an
	existing advanced tree or from the list view's current simple filters, and emits
	the serialized tree on apply.
-->
<template>
	<div class="advanced-filter">
		<div class="advanced-filter-body">
			<FilterGroup
				:group="root"
				:base-doctype="doctype"
				:parent-doctype="parentDoctype"
				:is-root="true"
				:depth="0"
			/>
		</div>

		<div class="advanced-filter-footer">
			<button class="btn btn-secondary btn-sm" @click="clear">{{ __("Clear filters") }}</button>
			<div class="advanced-filter-footer-right">
				<button class="btn btn-default btn-sm" @click="onClose">{{ __("Cancel") }}</button>
				<button class="btn btn-primary btn-sm" @click="apply">{{ __("Apply") }}</button>
			</div>
		</div>
	</div>
</template>

<script>
import FilterGroup from "./FilterGroup.vue";
import { seed_from_filters, clone_with_ids, serialize } from "./tree.js";

export default {
	name: "AdvancedFilter",
	components: { FilterGroup },
	props: {
		doctype: { type: String, required: true },
		parentDoctype: { type: String, default: null },
		filters: { type: Array, default: () => [] },
		filterTree: { type: Object, default: null },
		onApply: { type: Function, required: true },
		onClear: { type: Function, required: true },
		onClose: { type: Function, required: true },
	},
	data() {
		return {
			root: this.filterTree
				? clone_with_ids(this.filterTree)
				: seed_from_filters(this.filters, this.doctype),
		};
	},
	methods: {
		apply() {
			// `serialize` drops incomplete rules / empty groups and returns null when
			// nothing remains, which the caller treats as clearing the advanced filter.
			this.onApply(serialize(this.root));
		},
		clear() {
			this.onClear();
		},
	},
};
</script>

<style scoped>
.advanced-filter {
	display: flex;
	flex-direction: column;
	gap: 16px;
}
.advanced-filter-body {
	/* No inner overflow: an overflow container here would clip the field
	   picker's autocomplete dropdown. The dialog itself scrolls when tall. */
	padding: 4px 4px 8px;
}
.advanced-filter-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	border-top: 1px solid var(--border-color);
	padding-top: 12px;
}
.advanced-filter-footer-right {
	display: flex;
	gap: 8px;
}
</style>
