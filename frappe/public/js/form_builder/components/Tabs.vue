<script setup>
import Section from "./Section.vue";
import EditableInput from "./EditableInput.vue";
import draggable from "vuedraggable";
import { useStore } from "../store";
import { section_boilerplate, confirm_dialog } from "../utils";
import { ref, computed, nextTick } from "vue";

let store = useStore();

let dragged = ref(false);
let has_tabs = computed(() => store.form.layout.tabs.length > 1);
store.form.active_tab = store.form.layout.tabs[0].df.name;

function activate_tab(tab) {
	store.form.active_tab = tab.df.name;
	store.form.selected_field = tab.df;

	// scroll to active tab
	nextTick(() => {
		$(".tabs .tab.active")[0].scrollIntoView({
			behavior: "smooth",
			inline: "center"
		});
	});
}

function drag_over(tab) {
	!dragged.value &&
		setTimeout(() => {
			store.form.active_tab = tab.df.name;
		}, 500);
}

function add_new_tab() {
	let tab = {
		df: store.get_df("Tab Break", "", "Tab " + (store.form.layout.tabs.length + 1)),
		sections: [section_boilerplate()],
	};

	store.form.layout.tabs.push(tab);
	activate_tab(tab);
}

function add_new_section() {
	let section = section_boilerplate();
	store.current_tab.sections.push(section);
	store.form.selected_field = section.df;
}

function is_current_tab_empty() {
	// check if sections have columns and it contains fields
	return !store.current_tab.sections.some(
		section => section.columns.some(column => column.fields.length)
	);
}

function remove_tab() {
	if (store.is_customize_form && store.current_tab.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	} else if (store.has_standard_field(store.current_tab)) {
		delete_tab();
	} else if (is_current_tab_empty()) {
		delete_tab(true);
	} else {
		confirm_dialog(
			__("Delete Tab", null, "Title of confirmation dialog"),
			__("Are you sure you want to delete the tab? All the sections along with fields in the tab will be moved to the previous tab.", null, "Confirmation dialog message"),
			() => delete_tab(),
			__("Delete tab", null, "Button text"),
			() => delete_tab(true),
			__("Delete entire tab with sections", null, "Button text")
		);
	}
}

function delete_tab(with_children) {
	let tabs = store.form.layout.tabs;
	let index = tabs.indexOf(store.current_tab);

	if (!with_children) {
		if (index > 0) {
			let prev_tab = tabs[index - 1];
			if (!is_current_tab_empty()) {
				// move all sections from current tab to previous tab
				prev_tab.sections = [...prev_tab.sections, ...store.current_tab.sections];
			}
		} else {
			// create a new tab and push sections to it
			tabs.unshift({
				df: store.get_df("Tab Break", "", __("Details")),
				sections: store.current_tab.sections,
				is_first: true,
			});
			index++;
		}
	}

	// remove tab
	tabs.splice(index, 1);

	// activate previous tab
	let prev_tab_index = index == 0 ? 0 : index - 1;
	store.form.active_tab = tabs[prev_tab_index].df.name;
	store.form.selected_field = null;
}
</script>

<template>
	<div class="tab-header" v-if="!(store.form.layout.tabs.length == 1 && store.read_only)">
		<draggable
			v-show="has_tabs"
			class="tabs"
			v-model="store.form.layout.tabs"
			group="tabs"
			filter="[data-has-std-field='true']"
			:prevent-on-filter="false"
			:animation="200"
			:easing="store.get_animation"
			item-key="id"
			:disabled="store.read_only"
		>
			<template #item="{ element }">
				<div
					:class="['tab', store.form.active_tab == element.df.name ? 'active' : '']"
					:title="element.df.fieldname"
					:data-is-custom="element.df.is_custom_field"
					:data-has-std-field="store.has_standard_field(element)"
					@click.stop="activate_tab(element)"
					@dragstart="dragged = true"
					@dragend="dragged = false"
					@dragover="drag_over(element)"
				>
					<EditableInput
						:text="element.df.label"
						:placeholder="__('Tab Label')"
						v-model="element.df.label"
					/>
				</div>
			</template>
		</draggable>
		<div class="tab-actions" :hidden="store.read_only">
			<button
				class="new-tab-btn btn btn-xs"
				:class="{ 'no-tabs': !has_tabs }"
				:title="__('Add new tab')"
				@click="add_new_tab"
			>
				<div v-if="has_tabs" v-html="frappe.utils.icon('add', 'sm')"></div>
				<div class="add-btn-text" v-else>
					{{ __("Add new tab") }}
				</div>
			</button>
			<button
				v-if="has_tabs"
				class="remove-tab-btn btn btn-xs"
				:title="__('Remove selected tab')"
				@click="remove_tab"
			>
				<div v-html="frappe.utils.icon('remove', 'sm')"></div>
			</button>
		</div>
	</div>

	<div class="tab-contents">
		<div
			class="tab-content"
			v-for="(tab, i) in store.form.layout.tabs"
			:key="i"
			:class="[store.form.active_tab == tab.df.name ? 'active' : '']"
		>
			<draggable
				class="tab-content-container"
				v-model="tab.sections"
				group="sections"
				filter="[data-has-std-field='true']"
				:prevent-on-filter="false"
				:animation="200"
				:easing="store.get_animation"
				item-key="id"
				:disabled="store.read_only"
			>
				<template #item="{ element }">
					<Section
						:tab="tab"
						:section="element"
						:data-is-custom="element.df.is_custom_field"
						:data-has-std-field="store.has_standard_field(element)"
					/>
				</template>
			</draggable>
			<div class="empty-tab" :hidden="store.read_only">
				<div>{{ __("Drag & Drop a section here from another tab") }}</div>
				<div>{{ __("OR") }}</div>
				<button class="btn btn-default btn-sm" @click="add_new_section">
					{{ __("Add a new section") }}
				</button>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.tab-header {
	display: flex;
	justify-content: space-between;
	min-height: 53px;
	align-items: center;
	background-color: var(--fg-color);
	border-bottom: 1px solid var(--border-color);
	padding-left: var(--padding-xs);
	border-top-left-radius: var(--border-radius);
	border-top-right-radius: var(--border-radius);

	&:hover {
		.tab-actions .btn {
			opacity: 1 !important;
		}
	}

	.tabs {
		display: flex;
		flex: 1;
		overflow-x: auto;
		width: 0px;
	}

	.tab-actions {
		margin-right: 20px;

		.btn {
			opacity: 0;
			padding: 2px;
			margin-left: 4px;
			box-shadow: none;

			.add-btn-text {
				padding: 4px 8px;
			}

			&:hover {
				background-color: var(--border-color);
			}
		}

		.no-tabs {
			opacity: 1;
			margin-left: 15px;
		}
	}

	.tab {
		position: relative;
		padding: var(--padding-md);
		color: var(--text-muted);
		min-width: max-content;
		cursor: pointer;

		&::before {
			content: "";
			position: absolute;
			left: 0;
			right: 0;
			bottom: 0;
			margin: 0 var(--margin-md);
			width: auto;
			border-bottom: 1px solid transparent;
		}

		&:hover::before {
			border-color: var(--gray-300);
		}

		&.active {
			font-weight: 600;
			color: var(--text-color);

			&::before {
				border-color: var(--primary);
			}
		}
	}
}

.tab-contents {
	max-height: calc(100vh - 210px);
	overflow-y: auto;
	border-radius: var(--border-radius);
	min-height: 70px;

	.tab-content {
		display: none;
		position: relative;

		&.active {
			display: block;
		}

		.tab-content-container {
			min-height: 4rem;
			background-color: var(--field-placeholder-color);
			border-radius: var(--border-radius);

			&:empty {
				height: 7rem;
				margin: 1rem;

				& + .empty-tab {
					display: flex;
					flex-direction: column;
					align-items: center;
					position: absolute;
					top: 0;
					gap: 5px;
					width: 100%;
					padding: 15px;

					&button:hover {
						background-color: var(--border-color);
					}
				}
			}

			& + .empty-tab {
				display: none;
			}
		}
	}
}
</style>
