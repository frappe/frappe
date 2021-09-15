<template>
	<div class="letterhead">
		<div class="mb-2 d-flex justify-content-end">
			<button
				class="btn btn-default btn-xs btn-edit"
				@click="toggle_edit_letterhead"
			>
				{{ !$store.edit_letterhead ? __("Edit") : __("Done") }}
			</button>
			<button
				v-if="type == 'Header'"
				class="ml-2 btn btn-default btn-xs btn-change-letterhead"
				@click="change_letterhead"
			>
				{{ __("Change Letter Head") }}
			</button>
		</div>
		<div
			v-if="letterhead && !$store.edit_letterhead"
			v-html="letterhead[field]"
		></div>
		<div v-show="letterhead && $store.edit_letterhead" ref="editor"></div>
	</div>
</template>
<script>
import { storeMixin } from "./store";
export default {
	name: "LetterHeadEditor",
	props: ["type"],
	mixins: [storeMixin],
	mounted() {
		if (!this.letterhead) {
			frappe
				.call("frappe.client.get_default", { key: "letter_head" })
				.then(r => {
					if (r.message) {
						this.$store.change_letterhead(r.message);
					}
				});
		}
	},
	methods: {
		toggle_edit_letterhead() {
			if (this.$store.edit_letterhead) {
				this.$store.edit_letterhead = false;
				return;
			}
			this.$store.edit_letterhead = true;
			if (!this.control) {
				this.control = frappe.ui.form.make_control({
					parent: this.$refs.editor,
					df: {
						fieldname: "letterhead",
						fieldtype: "Comment",
						change: () => {
							this.letterhead._dirty = true;
							this.letterhead[
								this.field
							] = this.control.get_value();
						}
					},
					render_input: true,
					only_input: true,
					no_wrapper: true
				});
			}
			this.control.set_value(this.letterhead[this.field]);
		},
		change_letterhead() {
			let d = new frappe.ui.Dialog({
				title: __("Change Letter Head"),
				fields: [
					{
						label: __("Letter Head"),
						fieldname: "letterhead",
						fieldtype: "Link",
						options: "Letter Head"
					}
				],
				primary_action: ({ letterhead }) => {
					if (letterhead) {
						this.$store.change_letterhead(letterhead);
					}
					d.hide();
				}
			});
			d.show();
		}
	},
	computed: {
		field() {
			return {
				Header: "content",
				Footer: "footer"
			}[this.type];
		}
	}
};
</script>
<style>
.letterhead {
	position: relative;
	border: 1px solid var(--dark-border-color);
	border-radius: var(--border-radius);
	padding: 1rem;
	margin-bottom: 1rem;
}
</style>
