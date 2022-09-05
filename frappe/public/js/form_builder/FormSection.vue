<template>
	<div class="form-section-container" v-if="!section.remove">
		<div class="form-section">
			<div class="section-header">
				<input
					class="input-section-label"
					type="text"
					:placeholder="__('Section Title')"
					v-model="section.label"
				/>
				<div class="d-flex align-items-center">
					<div class="dropdown">
						<button
							class="btn btn-xs btn-section dropdown-button"
							data-toggle="dropdown"
						>
							<svg class="icon icon-sm">
								<use href="#icon-dot-horizontal"></use>
							</svg>
						</button>
						<div
							class="dropdown-menu dropdown-menu-right"
							role="menu"
						>
							<button
								v-for="(option, i) in section_options"
								:key="i"
								class="dropdown-item"
								@click="option.action"
							>
								{{ option.label }}
							</button>
						</div>
					</div>
				</div>
			</div>
			<div class="row section-columns">
				<div
					class="column col"
					v-for="(column, i) in section.columns"
					:key="i"
				>
					<draggable
						class="drag-container"
						:style="{
							backgroundColor: column.fields.length
								? null
								: 'var(--gray-50)'
						}"
						v-model="column.fields"
						group="fields"
						:animation="150"
					>
						<Field
							v-for="df in get_fields(column)"
							:key="df.fieldname"
							:df="df"
						/>
					</draggable>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import { storeMixin } from "./store";

export default {
	name: "FormSection",
	mixins: [storeMixin],
	props: ["section"],
	components: {
		draggable,
		Field
	},
	methods: {
		add_column() {
			if (this.section.columns.length < 4) {
				this.section.columns.push({
					label: "",
					fieldtype: "Column Break",
					new_field: true,
					fields: []
				});
			}
		},
		remove_column() {
			if (this.section.columns.length <= 1) return;

			let columns = this.section.columns.slice();
			let last_column_fields = columns.slice(-1)[0].fields.slice();
			let index = columns.length - 1;
			columns = columns.slice(0, index);
			let last_column = columns[index - 1];
			last_column.fields = [...last_column.fields, ...last_column_fields];

			this.$set(this.section, "columns", columns);
		},
		get_fields(column) {
			return column.fields.filter(df => !df.remove);
		}
	},
	computed: {
		section_options() {
			return [
				{
					label: __("Add section above"),
					action: () => this.$emit("add_section_above")
				},
				{
					label: __("Add column"),
					action: this.add_column,
					condition: () => this.section.columns.length < 4
				},
				{
					label: __("Remove column"),
					action: this.remove_column,
					condition: () => this.section.columns.length > 1
				},
				{
					label: __("Remove section"),
					action: () => this.$set(this.section, "remove", true)
				}
			].filter(option => (option.condition ? option.condition() : true));
		}
	}
};
</script>

<style lang="scss" scoped>
.form-section-container {
	&:not(:last-child) {
		margin-bottom: 1rem;
	}
	.form-section {
		background-color: white;
		border: 1px solid var(--dark-border-color);
		border-radius: var(--border-radius);
		padding: 1rem;
		cursor: pointer;

		&:not(:first-child) {
			margin-top: 1rem;
		}

		.section-header {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding-bottom: 0.75rem;

			.input-section-label {
				border: 1px solid transparent;
				border-radius: var(--border-radius);
				font-size: var(--text-md);
				font-weight: 600;

				&:focus {
					border-color: var(--border-color);
					outline: none;
					background-color: var(--control-bg);
				}

				&::placeholder {
					font-style: italic;
					font-weight: normal;
				}
			}

			.btn-section {
				padding: var(--padding-xs);
				box-shadow: none;

				&:hover {
					background-color: var(--bg-light-gray);
				}
			}
		}

		.section-columns {
			margin-left: -8px;
			margin-right: -8px;

			.column {
				padding-left: 8px;
				padding-right: 8px;

				.drag-container {
					height: 100%;
					min-height: 2rem;
					border-radius: var(--border-radius);
				}
			}
		}
	}
}
</style>
