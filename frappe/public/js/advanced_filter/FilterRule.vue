<!--
	A single filter rule: field picker + operator + value, mirroring one row of the
	legacy filter UI but as a leaf of the advanced filter tree. The field picker and
	value control reuse Frappe's own widgets, and the operator list comes from the
	shared filter_conditions module, so this row behaves exactly like a simple filter.
-->
<template>
	<div class="filter-rule">
		<div ref="field" class="filter-rule-field"></div>

		<select
			class="form-control input-xs filter-rule-operator"
			:value="rule.operator"
			:disabled="!conditions.length"
			@change="on_operator_change($event.target.value)"
		>
			<option v-for="[op, label] in conditions" :key="op" :value="op">{{ label }}</option>
		</select>

		<div class="filter-rule-value">
			<ControlValue
				v-if="df"
				:key="df.fieldname"
				:df="df"
				:value="rule.value"
				:condition="rule.operator"
				@update:value="rule.value = $event"
			/>
			<input v-else class="form-control input-xs" disabled :placeholder="__('Value')" />
		</div>

		<button
			class="btn btn-xs filter-rule-remove"
			:title="__('Remove')"
			@click="$emit('remove')"
		>
			<svg class="icon icon-sm"><use href="#icon-close"></use></svg>
		</button>
	</div>
</template>

<script>
import ControlValue from "./ControlValue.vue";

export default {
	name: "FilterRule",
	components: { ControlValue },
	props: {
		rule: { type: Object, required: true },
		baseDoctype: { type: String, required: true },
		parentDoctype: { type: String, default: null },
	},
	emits: ["remove"],
	data() {
		return {
			df: null, // docfield prepared for the value control
			conditions: [], // valid [operator, label] pairs for the chosen field
			selected_doctype: null,
		};
	},
	mounted() {
		this.make_field_select();
	},
	methods: {
		make_field_select() {
			this.field_select = new frappe.ui.FieldSelect({
				parent: $(this.$refs.field),
				doctype: this.baseDoctype,
				parent_doctype: this.parentDoctype,
				input_class: "input-xs",
				select: (doctype, fieldname) => this.on_field_select(doctype, fieldname),
			});

			if (this.rule.fieldname) {
				const doctype = this.rule.doctype || this.baseDoctype;
				this.field_select.set_value(doctype, this.rule.fieldname);
				this.selected_doctype = doctype;
				this.recompute({ reset_operator: false });
			}
		},

		on_field_select(doctype, fieldname) {
			this.selected_doctype = doctype;
			// Keep an explicit doctype only when it differs from the list's doctype.
			this.rule.doctype = doctype === this.baseDoctype ? null : doctype;
			this.rule.fieldname = fieldname;
			this.recompute({ reset_operator: true });
		},

		on_operator_change(operator) {
			this.rule.operator = operator;
			// Switching operator can change the value control (e.g. Between -> DateRange).
			this.recompute({ reset_operator: false });
		},

		get_original_docfield() {
			const fields = (this.field_select.fields_by_name || {})[this.selected_doctype] || {};
			return fields[this.rule.fieldname];
		},

		recompute({ reset_operator }) {
			const original = this.get_original_docfield();
			if (!original) {
				this.df = null;
				this.conditions = [];
				return;
			}

			const fc = frappe.ui.filter_conditions;

			// Operator choices are based on the field's true type.
			this.conditions = fc.get_valid_conditions_for_field(original);

			const is_valid = this.conditions.some(([op]) => op === this.rule.operator);
			if (reset_operator || !is_valid) {
				this.rule.operator =
					!reset_operator && is_valid
						? this.rule.operator
						: fc.filter_utils.get_default_condition(original);
			}

			// Build the docfield used to render the value control.
			const df = fc.filter_utils.prepare_filter_docfield(original);

			const override = fc.get_fieldtype_override(df, this.rule.operator);
			fc.filter_utils.set_fieldtype(df, override, this.rule.operator);
			this.df = df;
		},
	},
};
</script>

<style scoped>
.filter-rule {
	display: flex;
	align-items: center;
	gap: 8px;
}
.filter-rule-field {
	flex: 0 0 200px;
}
.filter-rule-operator {
	flex: 0 0 150px;
}
.filter-rule-value {
	flex: 1 1 auto;
	min-width: 0;
}
.filter-rule-remove {
	flex: 0 0 auto;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 26px;
	height: 26px;
	padding: 0;
	border: none;
	background: transparent;
	color: var(--text-muted);
}
.filter-rule-remove:hover {
	color: var(--text-color);
}

/*
 * The field picker and value input are created by frappe.ui.form.make_control,
 * so their elements only receive scoped styles through :deep(). Give every
 * control the same visible boundary so the row reads as distinct editable fields
 * (and the value control's own clear icon stays inside its box, away from the
 * remove button).
 */
.filter-rule-operator,
.filter-rule :deep(.form-control) {
	/* A white surface (vs the grey group background) plus a defined border so each
	   control reads as a distinct field. The default --control-bg equals the group
	   background (both --gray-100 in the light theme), which makes them blend. */
	background-color: var(--card-bg);
	border: 1px solid var(--gray-300);
	border-radius: var(--border-radius);
}
.filter-rule-value :deep(.form-control),
.filter-rule-value :deep(.awesomplete) {
	width: 100%;
}
</style>
