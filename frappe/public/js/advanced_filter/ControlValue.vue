<!--
	Thin Vue wrapper around frappe.ui.form.make_control.

	Rendering the value input through the same control factory the simple filter
	uses guarantees byte-for-byte parity (DateRange for Between, MultiSelect for
	in, Link autocomplete for links, Select for is/Check, etc.) instead of
	reimplementing each control. The parent passes a `df` that has already been run
	through the shared set_fieldtype mapping.
-->
<template>
	<div ref="control" class="advanced-filter-value"></div>
</template>

<script>
export default {
	name: "ControlValue",
	props: {
		df: { type: Object, required: true },
		value: { default: "" },
		condition: { type: String, default: "=" },
	},
	emits: ["update:value"],
	computed: {
		// Rebuild the control whenever the field, its rendered type, or the operator
		// changes (e.g. switching to "Between" turns a Date into a DateRange).
		control_key() {
			return [this.df.fieldname, this.df.fieldtype, this.df.options, this.condition].join("::");
		},
	},
	watch: {
		control_key() {
			this.make_control();
		},
	},
	mounted() {
		this.make_control();
	},
	beforeUnmount() {
		this.destroy_control();
	},
	methods: {
		destroy_control() {
			this.control = null;
			if (this.$refs.control) this.$refs.control.innerHTML = "";
		},

		make_control() {
			this.destroy_control();

			const df = { ...this.df, input_class: "input-xs" };
			const field = frappe.ui.form.make_control({
				df,
				parent: this.$refs.control,
				only_input: true,
			});
			field.refresh();
			this.control = field;
			this.set_value(this.value);

			const emit = () => {
				const val = frappe.ui.filter_conditions.filter_utils.get_selected_value(
					field,
					this.condition
				);
				this.$emit("update:value", val);
			};

			field.$input && field.$input.on("change", emit);
			field.$input && field.$input.on("focusout", emit);
			// MultiSelect / DateRange and similar emit on their inner inputs.
			$(field.wrapper).find(":input").on("change", emit);
		},

		set_value(value) {
			if (!this.control || value === undefined || value === null || value === "") return;

			let v = value;
			if (["in", "not in"].includes(this.condition) && Array.isArray(v)) {
				v = v.some((item) => String(item).includes(",")) ? JSON.stringify(v) : v.join(",");
			}
			this.control.set_value(Array.isArray(v) ? v : String(v));
		},
	},
};
</script>
