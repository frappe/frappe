<template>
	<div class="html-editor">
		<div class="d-flex justify-content-end">
			<button
				class="btn btn-default btn-xs btn-edit"
				@click="toggle_edit"
			>
				{{ !editing ? buttonLabel : __("Done") }}
			</button>
		</div>
		<div v-if="!editing" v-html="value"></div>
		<div v-show="editing" ref="editor"></div>
	</div>
</template>
<script>
export default {
	name: "HTMLEditor",
	props: ["value", "button-label"],
	data() {
		return {
			editing: false
		};
	},
	methods: {
		toggle_edit() {
			if (this.editing) {
				this.$emit("change", this.get_value());
				this.editing = false;
				return;
			}

			this.editing = true;
			if (!this.control) {
				this.control = frappe.ui.form.make_control({
					parent: this.$refs.editor,
					df: {
						fieldname: "editor",
						fieldtype: "HTML Editor",
						min_lines: 10,
						max_lines: 30,
						change: () => {
							this.$emit("change", this.get_value());
						}
					},
					render_input: true
				});
			}
			this.control.set_value(this.value);
		},
		get_value() {
			return frappe.dom.remove_script_and_style(this.control.get_value());
		}
	}
};
</script>
<style>
.html-editor {
	position: relative;
	border: 1px solid var(--dark-border-color);
	border-radius: var(--border-radius);
	padding: 1rem;
	margin-bottom: 1rem;
}

.html-editor:last-child {
	margin-bottom: 0;
}
</style>
