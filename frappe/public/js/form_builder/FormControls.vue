<template>
	<div class="layout-side-section">
		<div class="form-sidebar">
			<div class="search-box">
				<input
					class="search-input form-control form-control-sm"
					type="text"
					:placeholder="__('Search fields')"
					v-model="search_text"
				/>
				<span class="search-icon">
					<svg class="icon icon-sm">
						<use href="#icon-search"></use>
					</svg>
				</span>
			</div>
			<div class="tabs-container">
				<div
					class="sidebar-tab"
					:class="{ 'active': active_tab == tab }"
					v-for="(tab, i) in ['Fields', 'Data']"
					:key="i"
					@click="active_tab = tab"
				>
					{{ tab }}
				</div>
			</div>
			<div class="tabs-content">
				<div
					:active="active_tab == 'Fields'"
					class="sidebar-menu tab-content"
				>
					<draggable
						class="fields-container"
						:list="fields"
						:group="{ name: 'fields', pull: 'clone', put: false }"
						:sort="false"
						:clone="clone_field"
					>
						<div
							class="field"
							v-for="(field, i) in fields"
							:key="i"
							:title="field.df.fieldtype"
						>
							{{ field.df.fieldtype }}
						</div>
					</draggable>
				</div>
				<div
					:active="active_tab == 'Data'"
					class="tab-content"
				>
					<div class="control-data">
						<div v-if="selected_field">
							<div
								class="field"
								v-for="(df, i) in docfield_df"
								:key="i"
							>
								<div class="label">{{ df.label }}</div>
								<div class="input">
									<input
										class="mb-2 form-control form-control-sm"
										type="text"
										v-model="selected_field[df.fieldname]"
									/>
								</div>
								<div class="description" v-if="df.description">{{ df.description }}</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
import draggable from "vuedraggable";
import { evaluate_depends_on_value } from "./utils";
import { storeMixin } from "./store";

export default {
	name: "FormControls",
	mixins: [storeMixin],
	components: {
		draggable
	},
	data() {
		return {
			search_text: "",
			active_tab: "Fields",
		};
	},
	watch: {
		selected_field() {
			this.active_tab = "Data";
		}
	},
	methods: {
		clone_field(field) {
			return field;
		}
	},
	computed: {
		fields() {
			let fields = frappe.model.all_fieldtypes
				.filter(df => {
					if (
						in_list(["Tab Break", "Section Break", "Column Break", "Fold"], df)
					) {
						return false;
					}
					if (this.search_text) {
						if (df.toLowerCase().includes(this.search_text.toLowerCase())) {
							return true;
						}
						return false;
					} else {
						return true;
					}
				})
				.map(df => {
					let out = {
						df: {
							label: "",
							fieldname: "",
							fieldtype: df,
							options: "",
						},
						table_columns: [],
						new_field: true,
					};
					return out;
				});

			return [...fields];
		},
		docfield_df() {
			let fields = this.docfields
				.filter(df => {
					if (
						in_list(["Tab Break", "Section Break", "Column Break", "Fold"], df.fieldtype) ||
						!df.label
					) {
						return false;
					}
					if (df.depends_on && !evaluate_depends_on_value(df.depends_on, this.selected_field)) {
						return false;
					}

					if (this.search_text) {
						if (df.label.toLowerCase().includes(this.search_text.toLowerCase()) ||
							df.fieldname.toLowerCase().includes(this.search_text.toLowerCase())) {
							return true;
						}
						return false;
					} else {
						return true;
					}
				})

			return [...fields];
		}
	}
};
</script>

<style lang="scss" scoped>
.layout-side-section {
	padding: 0;

	.search-box {
		display: flex;
		position: relative;
		margin-bottom: 0.5rem;

		.search-input {
			padding-left: 30px;
		}

		.search-icon {
			position: absolute;
			margin-left: 8px;
			display: flex;
			align-items: center;
			height: 100%;
		}
	}

	.tabs-container {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;

		.sidebar-tab {
			display: flex;
			justify-content: center;
			align-items: center;
			width: 100%;
			height: 2rem;
			border-radius: var(--border-radius-md);
			border: 1px solid var(--dark-border-color);
			cursor: pointer;

			&:not(:first-child) {
				border-left: none;
				border-top-left-radius: 0;
				border-bottom-left-radius: 0;
			}

			&:first-child {
				border-top-right-radius: 0;
				border-bottom-right-radius: 0;
			}

			&.active {
				background-color: var(--bg-gray);
			}
		}
	}

	.tabs-content {
		.tab-content {
			display: none;

			&[active] {
				display: block;
			}

			.fields-container {
				max-height: calc(100vh - 15rem);
				overflow-y: auto;

				.field {
					display: flex;
					justify-content: space-between;
					align-items: center;
					background-color: var(--bg-light-gray);
					border-radius: var(--border-radius);
					border: 1px dashed var(--gray-400);
					padding: 0.5rem 0.75rem;
					margin: 5px;
					margin-top: 0;
					font-size: var(--text-sm);
					cursor: pointer;

					&:not(:first-child) {
						margin-top: 0.5rem;
					}
				}
			}

			.control-data {
				max-height: calc(100vh - 14rem);
				overflow-y: auto;

				.field {
					margin: 5px;
					margin-top: 0;
					margin-bottom: 1rem;

					.label {
						margin-bottom: 0.3rem;
					}
					.description {
						font-size: var(--text-sm);
						color: var(--text-muted);
					}
				}
			}
		}
	}

	.form-control {
		background: var(--control-bg-on-gray);
	}
}
</style>
