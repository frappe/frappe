<!--
	A filter group: an AND/OR conjunction over an ordered list of children, each of
	which is itself a rule or a nested group (arbitrary depth). The conjunction
	column on the left reads "Where" for the first child and the group's conjunction
	for the rest. Because a group has a
	single conjunction, changing the dropdown on any row re-labels the whole group.
-->
<template>
	<div class="filter-group" :class="{ 'is-root': isRoot }">
		<div v-for="(child, index) in group.children" :key="child.id" class="filter-group-row">
			<div class="filter-conjunction">
				<span v-if="index === 0" class="conjunction-label text-muted">{{ __("Where") }}</span>
				<select
					v-else-if="index === 1"
					class="form-control input-xs conjunction-select"
					:value="group.conjunction"
					@change="group.conjunction = $event.target.value"
				>
					<option value="and">{{ __("And") }}</option>
					<option value="or">{{ __("Or") }}</option>
				</select>
				<span v-else class="conjunction-label text-muted">{{ conjunction_label }}</span>
			</div>

			<div class="filter-child">
				<FilterRule
					v-if="child.type === 'rule'"
					:rule="child"
					:base-doctype="baseDoctype"
					:parent-doctype="parentDoctype"
					@remove="remove(index)"
				/>
				<div v-else class="nested-group">
					<div class="nested-group-toolbar">
						<span class="nested-group-label text-muted">{{ __("Filter group") }}</span>
						<button
							class="nested-group-remove"
							:title="__('Remove group')"
							@click="remove(index)"
						>
							<svg class="icon icon-sm"><use href="#icon-close"></use></svg>
						</button>
					</div>
					<FilterGroup
						:group="child"
						:base-doctype="baseDoctype"
						:parent-doctype="parentDoctype"
						:depth="depth + 1"
					/>
				</div>
			</div>
		</div>

		<div class="filter-group-actions">
			<button class="btn btn-xs btn-default add-rule" @click="add_rule">
				+ {{ __("Add filter rule") }}
			</button>
			<button v-if="depth < MAX_DEPTH" class="btn btn-xs btn-default add-group" @click="add_group">
				+ {{ __("Add filter group") }}
			</button>
		</div>
	</div>
</template>

<script>
import FilterRule from "./FilterRule.vue";
import { make_rule, make_group } from "./tree.js";

// Keep in sync with MAX_DEPTH in frappe/model/filter_tree.py.
const MAX_DEPTH = 20;

export default {
	name: "FilterGroup",
	// FilterRule must be registered explicitly; FilterGroup resolves its own
	// recursive use by `name`.
	components: { FilterRule },
	props: {
		group: { type: Object, required: true },
		baseDoctype: { type: String, required: true },
		parentDoctype: { type: String, default: null },
		depth: { type: Number, default: 0 },
		isRoot: { type: Boolean, default: false },
	},
	data() {
		return { MAX_DEPTH };
	},
	computed: {
		conjunction_label() {
			return this.group.conjunction === "or" ? __("Or") : __("And");
		},
	},
	methods: {
		add_rule() {
			this.group.children.push(make_rule());
		},
		add_group() {
			// A fresh nested group starts with one empty rule so it is immediately usable.
			this.group.children.push(make_group("and", [make_rule()]));
		},
		remove(index) {
			this.group.children.splice(index, 1);
			// Never let the root collapse to nothing - keep one empty rule to edit.
			if (this.isRoot && !this.group.children.length) {
				this.group.children.push(make_rule());
			}
		},
	},
};
</script>

<style scoped>
.filter-group {
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.filter-group.is-root {
	gap: 10px;
}
.filter-group-row {
	display: flex;
	align-items: flex-start;
	gap: 8px;
}
.filter-conjunction {
	flex: 0 0 64px;
	padding-top: 4px;
	text-align: right;
}
.conjunction-label {
	font-size: var(--text-sm);
}
.conjunction-select {
	width: 64px;
}
.filter-child {
	flex: 1 1 auto;
	min-width: 0;
}
.nested-group {
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-md);
	padding: 8px 10px 10px;
	background-color: var(--subtle-fg, var(--gray-50));
}
.nested-group-toolbar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 6px;
}
.nested-group-label {
	font-size: var(--text-sm);
}
.nested-group-remove {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 24px;
	height: 24px;
	padding: 0;
	border: none;
	background: transparent;
	color: var(--text-muted);
}
.nested-group-remove:hover {
	color: var(--text-color);
}
.filter-group-actions {
	display: flex;
	gap: 8px;
	padding-left: 72px;
}
.filter-group.is-root > .filter-group-actions {
	padding-left: 72px;
}
</style>
