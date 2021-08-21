<template>
	<div class="print-format-section-container" v-if="!section.remove">
		<div class="print-format-section">
			<div class="section-header">
				<input
					class="input-section-label w-50"
					type="text"
					:placeholder="__('Section Title')"
					v-model="section.label"
				/>
				<div class="dropdown">
					<button
						class="btn btn-xs btn-section dropdown-button"
						data-toggle="dropdown"
					>
						<svg class="icon icon-sm">
							<use xlink:href="#icon-dot-horizontal"></use>
						</svg>
					</button>
					<div class="dropdown-menu dropdown-menu-right" role="menu">
						<button class="dropdown-item" @click="$emit('add_section_above')">
							{{ __("Add section above") }}
						</button>
						<button
							class="dropdown-item"
							@click="add_column"
							v-if="section.columns.length < 4"
						>
							{{ __("Add column") }}
						</button>
						<button
							class="dropdown-item"
							@click="add_page_break"
							v-if="!section.page_break"
						>
							{{ __("Add page break") }}
						</button>
						<button
							class="dropdown-item"
							@click="remove_page_break"
							v-if="section.page_break"
						>
							{{ __("Remove page break") }}
						</button>
						<button
							class="dropdown-item"
							@click="remove_column"
							v-if="section.columns.length > 1"
						>
							{{ __("Remove column") }}
						</button>
						<button
							class="dropdown-item"
							@click="$set(section, 'remove', true)"
						>
							{{ __("Remove section") }}
						</button>
					</div>
				</div>
			</div>
			<div class="row section-columns">
				<div class="column col" v-for="(column, i) in section.columns" :key="i">
					<draggable
						class="drag-container"
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
		<div class="my-4 text-muted text-center font-italic" v-if="section.page_break">
			{{ __("Page Break") }}
		</div>
	</div>
</template>

<script>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import { storeMixin } from "./store";

export default {
	name: "PrintFormatSection",
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
		add_page_break() {
			this.$set(this.section, "page_break", true);
		},
		remove_page_break() {
			this.$set(this.section, "page_break", false);
		},
		get_fields(column) {
			return column.fields.filter(df => !df.remove);
		}
	}
};
</script>

<style scoped>
.print-format-section-container:not(:last-child) {
	margin-bottom: 1rem;
}

.print-format-section {
	background-color: white;
	border: 1px solid var(--dark-border-color);
	border-radius: var(--border-radius);
	padding: 1rem;
	cursor: pointer;
}

.section-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding-bottom: 0.75rem;
}

.input-section-label {
	border: 1px solid transparent;
	border-radius: var(--border-radius);
	font-size: var(--text-md);
	font-weight: 600;
}

.input-section-label:focus {
	border-color: var(--border-color);
	outline: none;
	background-color: var(--control-bg);
}

.input-section-label::placeholder {
	font-style: italic;
	font-weight: normal;
}

.btn-section {
	padding: var(--padding-xs);
	box-shadow: none;
}

.btn-section:hover {
	background-color: var(--bg-light-gray);
}

.print-format-section:not(:first-child) {
	margin-top: 1rem;
}

.section-columns {
	margin-left: -8px;
	margin-right: -8px;
}

.column {
	padding-left: 8px;
	padding-right: 8px;
}

.drag-container {
	height: 100%;
	min-height: 2rem;
}
</style>
