<script setup>
import Section from "./Section.vue";
import EditableInput from "./EditableInput.vue";
import { useStore } from "../store";
import { section_boilerplate, confirm_dialog, is_touch_screen_device } from "../utils";
import draggable from "vuedraggable";
import { ref, computed } from "vue";
import { useMagicKeys, whenever } from "@vueuse/core";

const store = useStore();

// delete/backspace to delete the field
const { Backspace } = useMagicKeys();
whenever(Backspace, (value) => {
	if (value && selected.value && store.not_using_input && store.can_edit_layout) {
		remove_tab(store.current_tab, "", true);
	}
});

const dragged = ref(false);
const selected = computed(() => store.selected(store.current_tab.df.name));
const has_tabs = computed(() => store.form.layout.tabs.length > 1);
// a Web Form names the page the author is on from page 1; a DocType only grows a strip
// once it has two tabs
const has_tab_strip = computed(() => has_tabs.value || store.is_web_form);
// page 1 is implicit, so a form with one page has no Page Break row to delete
const can_remove_tab = computed(() => !store.is_web_form || has_tabs.value);
store.form.active_tab = store.form.layout.tabs[0].df.name;

function activate_tab(tab) {
	store.activate_tab(tab);
}

function drag_over(tab) {
	!dragged.value &&
		setTimeout(() => {
			store.form.active_tab = tab.df.name;
		}, 500);
}

function add_new_tab() {
	store.add_new_tab();
}

function add_new_section() {
	let section = section_boilerplate();
	store.current_tab.sections.push(section);
	store.form.selected_field = section.df;
}

function is_tab_empty(tab) {
	// check if sections have columns and it contains fields
	return !tab.sections.some((section) => section.columns.some((column) => column.fields.length));
}

function remove_tab(tab, event, force = false) {
	// is remove_tab_btn is not visible then return
	if (!event?.currentTarget?.offsetParent && !force) return;

	// page 1 always exists — the header hides its delete button, but Backspace bypasses that
	if (store.is_web_form && store.form.layout.tabs.length === 1) return;

	if (store.is_customize_form && store.current_tab.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	} else if (store.has_standard_field(store.current_tab)) {
		delete_tab(tab);
	} else if (is_tab_empty(tab)) {
		delete_tab(tab, true);
	} else {
		confirm_dialog(
			store.tab_text.delete_title,
			delete_tab_message(tab),
			() => delete_tab(tab),
			store.tab_text.delete_button,
			() => delete_tab(tab, true),
			store.tab_text.delete_with_fields
		);
	}
}

function delete_tab(tab, with_children) {
	let tabs = store.form.layout.tabs;
	let index = tabs.indexOf(tab);

	if (!with_children) {
		if (index > 0) {
			let prev_tab = tabs[index - 1];
			if (!is_tab_empty(tab)) {
				// move all sections from current tab to previous tab
				prev_tab.sections = [...prev_tab.sections, ...tab.sections];
			}
		} else if (store.is_web_form) {
			// no previous page, so move the fields forward into page 2
			let next_tab = tabs[1];
			if (!is_tab_empty(tab)) {
				next_tab.sections = [...tab.sections, ...next_tab.sections];
			}
		} else {
			// create a new tab and push sections to it
			tabs.unshift({
				df: store.get_df("Tab Break", "", __("Details")),
				sections: tab.sections,
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

// page 1 has no previous page, so its fields move forward instead (see delete_tab)
function delete_tab_message(tab) {
	if (store.is_web_form && store.form.layout.tabs.indexOf(tab) === 0) {
		return __(
			"Are you sure you want to delete the page? All the sections along with fields in the page will be moved to the next page.",
			null,
			"Confirmation dialog message"
		);
	}

	return store.tab_text.delete_message;
}
</script>

<template>
	<div class="tab-header" v-if="has_tab_strip">
		<draggable
			class="tabs"
			v-model="store.form.layout.tabs"
			group="tabs"
			:delay="is_touch_screen_device() ? 200 : 0"
			:animation="200"
			:easing="store.get_animation"
			item-key="id"
			:disabled="store.read_only"
		>
			<template #item="{ element }">
				<div
					:class="['tab', store.form.active_tab == element.df.name ? 'active' : '']"
					:title="element.df.fieldname"
					:data-is-user-generated="store.is_user_generated_field(element)"
					@click.stop="activate_tab(element)"
					@dragstart="dragged = true"
					@dragend="dragged = false"
					@dragover="drag_over(element)"
				>
					<!-- a Page Break row stores no label, so the builder numbers pages by position -->
					<span v-if="store.is_web_form">{{ element.df.label }}</span>
					<EditableInput
						v-else
						:text="element.df.label"
						:placeholder="__('Tab Label')"
						v-model="element.df.label"
					/>
					<button
						v-if="!store.is_layout_form && can_remove_tab"
						class="remove-tab-btn btn btn-xs"
						:title="store.tab_text.remove_title"
						@click.stop="remove_tab(element, $event)"
						:hidden="store.read_only"
					>
						<div v-html="frappe.utils.icon('x', 'xs')"></div>
					</button>
				</div>
			</template>
		</draggable>
		<div class="tab-actions" :hidden="!store.can_edit_layout">
			<button
				class="new-tab-btn btn btn-xs flex items-center gap-1"
				:title="store.tab_text.add_title"
				@click="add_new_tab"
			>
				<span v-html="frappe.utils.icon('plus', 'xs')"></span>
				{{ store.tab_text.add }}
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
				:delay="is_touch_screen_device() ? 200 : 0"
				:animation="200"
				:easing="store.get_animation"
				item-key="id"
				:disabled="store.read_only"
			>
				<template #item="{ element }">
					<Section
						:tab="tab"
						:section="element"
						:data-is-user-generated="store.is_user_generated_field(element)"
					/>
				</template>
			</draggable>
			<div class="empty-tab" :hidden="!store.can_edit_layout">
				<div v-if="has_tabs">{{ store.tab_text.drop_hint }}</div>
				<div v-if="has_tabs">{{ __("OR") }}</div>
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
	min-height: 42px;
	align-items: center;
	background-color: var(--fg-color);
	border-bottom: 1px solid var(--border-color);
	padding-left: var(--padding-xs);
	border-top-left-radius: var(--radius);
	border-top-right-radius: var(--radius);

	.tabs {
		display: flex;
		// only as wide as the tabs, so the add button sits beside the last one and the
		// strip scrolls only once it runs out of room
		flex: 0 1 auto;
		overflow-x: auto;
		min-width: 0;
	}

	.tab-actions {
		margin-right: 20px;
		flex: none;

		// reads as one more tab, not a button: no fill, only the text colour lifts
		.btn {
			background-color: transparent;
			box-shadow: none;
			color: var(--text-muted);
			// the plus follows the text colour in both themes
			--icon-stroke: currentColor;

			&:hover,
			&:focus,
			&:active {
				background-color: transparent;
				box-shadow: none;
				color: var(--text-color);
			}
		}
	}

	.tab {
		display: flex;
		align-items: center;
		position: relative;
		padding: 10px 18px 10px 15px;
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
				border-color: var(--border-primary);
			}
		}

		&:hover .remove-tab-btn {
			display: block;
		}

		.remove-tab-btn {
			position: absolute;
			right: -2px;
			display: none;
			padding: 2px;
		}
	}
}

.tab-contents {
	max-height: calc(100vh - 217px);
	overflow-y: auto;
	overflow-x: hidden;
	border-radius: var(--radius);
	min-height: 70px;

	.tab-content {
		display: none;
		position: relative;

		&.active {
			display: flex;
		}

		.tab-content-container {
			flex: 1;
			min-height: 4rem;
			border-radius: var(--radius);
			z-index: 1;

			&:empty {
				height: 7rem;
				margin: 1rem;

				& + .empty-tab {
					display: flex;
					flex-direction: column;
					align-items: center;
					justify-content: center;
					position: absolute;
					top: 0;
					bottom: 0;
					gap: 5px;
					width: 100%;
					padding: 15px;

					button {
						z-index: 2;
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
