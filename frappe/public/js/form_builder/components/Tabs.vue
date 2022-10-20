<script setup>
import Section from "./Section.vue";
import draggable from "vuedraggable";
import { useStore } from "../store";
import { ref, computed } from "vue";

let store = useStore();

let dragged = ref(false);
let layout = computed(() => store.layout);
let has_tabs = computed(() => layout.value.tabs.length > 1);
store.active_tab = layout.value.tabs[0].df.name;

function activate_tab(tab) {
	store.active_tab = tab.df.name;
	store.selected_field = tab.df;
}

function drag_over(tab) {
	!dragged.value &&
		setTimeout(() => {
			store.active_tab = tab.df.name;
		}, 500);
}

function add_section_above(section) {
	let sections = [];
	let current_tab = layout.value.tabs.find(tab => tab.df.name == store.active_tab);
	for (let _section of current_tab.sections) {
		if (_section === section) {
			sections.push({
				df: {
					name: frappe.utils.get_random(8),
					fieldtype: "Section Break"
				},
				new_field: true,
				columns: [
					{ df: { fieldtype: "Column Break" }, new_field: true, fields: [] },
					{ df: { fieldtype: "Column Break" }, new_field: true, fields: [] }
				]
			});
		}
		sections.push(_section);
	}
	current_tab.sections = sections;
}

function add_new_tab() {
	let tab = {
		df: {
			label: "Tab " + (layout.value.tabs.length + 1),
			name: frappe.utils.get_random(8),
			fieldtype: "Tab Break"
		},
		sections: [{
			df: {
				name: frappe.utils.get_random(8),
				fieldtype: "Section Break"
			},
			columns: [
				{ df: { fieldtype: "Column Break" }, fields: [], new_field: true },
				{ df: { fieldtype: "Column Break" }, fields: [], new_field: true }
			],
			new_field: true,
		}],
		new_field: true,
	}
	layout.value.tabs.push(tab);
	activate_tab(tab);
}

function remove_tab() {
	let current_tab = layout.value.tabs.find(tab => tab.df.name == store.active_tab);
	layout.value.tabs = layout.value.tabs.filter(tab => tab !== current_tab);
	store.active_tab = layout.value.tabs[0].df.name;
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
			:animation="200"
			item-key="id"
		>
			<template #item="{ element }">
				<div
					:class="['tab', store.active_tab == element.df.name ? 'active' : '']"
					@click="activate_tab(element)"
					@dragstart="dragged = true"
					@dragend="dragged = false"
					@dragover="drag_over(element)"
				>
					<div v-if="element.df.label">{{ element.df.label }}</div>
					<i class="text-muted" v-else> {{ __("No Label") }}</i>
				</div>
			</template>
		</draggable>
		<div class="tab-actions">
			<button
				class="new-tab-btn btn btn-xs"
				:class="{ 'no-tabs' : !has_tabs }"
				:title="__('Add new tab')"
				@click="add_new_tab()"
			>
				<svg class="icon icon-sm" v-if="has_tabs">
					<use href="#icon-add"></use>
				</svg>
				<div class="add-btn-text" v-else>
					{{ __('Add new tab') }}
				</div>
			</button>
			<button
				v-if="has_tabs"
				class="remove-tab-btn btn btn-xs"
				:title="__('Remove selected tab')"
				@click="remove_tab()"
			>
				<svg class="icon icon-sm">
					<use href="#icon-close"></use>
				</svg>
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
				:animation="200"
				item-key="id"
			>
				<template #item="{ element }">
					<Section :section="element" @add_section_above="add_section_above(element)" />
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
	}

	.tab-actions {
		margin-right: 20px;

		.btn {
			opacity: 0;
			padding: 2px;
			margin-left: 8px;

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
	}
}
</style>
