<template>
	<button
		class="btn btn-xs btn-default margin-text"
		:class="{ 'text-extra-muted': !value }"
		:style="styles"
		@click="edit"
		:title="__('Edit {0}', [label])"
	>
		{{ value || label }}
	</button>
</template>
<script>
import { storeMixin } from "./store";

export default {
	name: "MarginText",
	props: ["position"],
	mixins: [storeMixin],
	methods: {
		edit() {
			let d = new frappe.ui.Dialog({
				title: __("Edit {0}", [this.label]),
				fields: [
					{
						label: __("Select Template"),
						fieldname: "helper",
						fieldtype: "Select",
						options: Object.keys(this.helpers),
						change: () => {
							this.set_helper(d.get_value("helper"));
						}
					},
					{
						label: this.label,
						fieldname: "text",
						fieldtype: "Data",
						description:
							"Use jinja blocks for dynamic content. For e.g., {{ doc.name }}"
					}
				],
				primary_action: ({ text }) => {
					this.$set(this.layout, "text_" + this.position, text);
					d.hide();
				},
				secondary_action_label: __("Clear"),
				secondary_action: () => {
					d.set_value("text", "");
				}
			});
			d.show();
			d.set_value("text", this.value);
			this.dialog = d;
		},
		set_helper(helper) {
			let value = this.helpers[helper];
			if (value) {
				this.dialog.set_value("text", value);
			}
		}
	},
	computed: {
		value() {
			let text = this.layout["text_" + this.position];
			return text;
		},
		label() {
			return {
				top_left: __("Top Left Text"),
				top_center: __("Top Center Text"),
				top_right: __("Top Right Text"),
				bottom_left: __("Bottom Left Text"),
				bottom_center: __("Bottom Center Text"),
				bottom_right: __("Bottom Right Text")
			}[this.position];
		},
		helpers() {
			return {
				"Page number (x of y)": 'counter(page) " of " counter(pages)',
				"Document Name": '"{{ doc.name }}"'
			};
		},
		styles() {
			let styles = {};
			if (this.position.includes("top")) {
				styles.top = "0.5rem";
			}
			if (this.position.includes("bottom")) {
				styles.bottom = "0.5rem";
			}
			if (this.position.includes("left")) {
				styles.left = this.print_format.margin_left + "mm";
			}
			if (this.position.includes("right")) {
				styles.right = this.print_format.margin_right + "mm";
			}
			if (this.position.includes("center")) {
				styles.left = "50%";
				styles.transform = "translateX(-50%)";
			}
			return styles;
		}
	}
};
</script>
<style scoped>
.margin-text {
	position: absolute;
	z-index: 1;
	max-width: 10rem;
	white-space: nowrap;
	text-overflow: ellipsis;
	overflow: hidden;
}
</style>
