<script setup>
import Section from "./Section.vue";
import draggable from "vuedraggable";
import { useStore } from "../store";
import { section_boilerplate } from "../utils";
import { ref, computed, nextTick } from "vue";

let store = useStore();

let dragged = ref(false);
let layout = computed(() => store.layout);
let has_tabs = computed(() => layout.value.tabs.length > 1);
store.active_tab = layout.value.tabs[0].df.name;

let current_tab = computed(() => {
	return layout.value.tabs.find(t => t.df.name === store.active_tab);
});

function activate_tab(tab) {
	store.active_tab = tab.df.name;
	store.selected_field = tab.df;

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
			store.active_tab = tab.df.name;
		}, 500);
}

function add_new_tab() {
	let tab = {
		df: store.get_df("Tab Break", "", "Tab " + (layout.value.tabs.length + 1)),
		sections: [section_boilerplate()],
	};

	layout.value.tabs.push(tab);
	activate_tab(tab);
}

function remove_tab() {
	if (store.is_customize_form && current_tab.value.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	}

	// move all sections from current tab to previous tab
	let tabs = layout.value.tabs;
	let index = tabs.indexOf(current_tab.value);

	if (index > 0) {
		let prev_tab = tabs[index - 1];
		prev_tab.sections = [...prev_tab.sections, ...current_tab.value.sections];
	} else {
		// create a new tab and push sections to it
		tabs.unshift({
			df: store.get_df("Tab Break"),
			sections: current_tab.value.sections,
			is_first: true,
		});
		index++;
	}

	// remove tab
	tabs.splice(index, 1);

	// activate previous tab
	let prev_tab_index = index == 0 ? 0 : index - 1;
	store.active_tab = tabs[prev_tab_index].df.name;
	store.selected_field = null;
}
</script>

<template>
	<div class="tab-header">
		<draggable
			v-show="has_tabs"
			class="tabs"
			v-model="layout.tabs"
			group="tabs"
			filter="[data-is-custom='0']"
			:animation="200"
			item-key="id"
			:disabled="store.read_only"
		>
			<template #item="{ element }">
				<div
					:class="['tab', store.active_tab == element.df.name ? 'active' : '']"
					:title="element.df.fieldname"
					:data-is-custom="store.is_custom(element)"
					@click.stop="activate_tab(element)"
					@dragstart="dragged = true"
					@dragend="dragged = false"
					@dragover="drag_over(element)"
				>
					<div v-if="element.df.label">{{ element.df.label }}</div>
					<i class="text-muted" v-else> {{ __("No Label") }}</i>
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
				<div v-html="frappe.utils.icon('close', 'sm')"></div>
			</button>
		</div>
	</div>

	<div class="tab-contents">
		<div
			class="tab-content"
			v-for="(tab, i) in layout.tabs"
			:key="i"
			:class="[store.active_tab == tab.df.name ? 'active' : '']"
		>
			<draggable
				class="tab-content-container"
				v-model="tab.sections"
				group="sections"
				filter="[data-is-custom='0']"
				:animation="200"
				item-key="id"
				:disabled="store.read_only"
			>
				<template #item="{ element }">
					<Section
						:tab="tab"
						:section="element"
						:data-is-custom="store.is_custom(element)"
					/>
				</template>
			</draggable>
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
		padding: var(--padding-md) 0;
		margin: 0 var(--margin-md);
		color: var(--text-muted);
		border-bottom: 1px solid var(--white);
		min-width: max-content;
		cursor: pointer;

		.tab-name {
			outline: none;
			border: none;
			width: fit-content;
		}

		&:hover {
			border-bottom: 1px solid var(--gray-300);
		}

		&.active {
			font-weight: 600;
			color: var(--text-color);
			border-bottom: 1px solid var(--primary);
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

		&.active {
			display: block;
		}

		.tab-content-container {
			min-height: 4rem;
		}
	}
}
</style>
