<template>
	<div class="tree-node" :class="{ opened: node.open }">
		<span
			ref="reference"
			class="tree-link"
			@click="emit('node-click', node)"
			:class="{ active: node.value === selected_node.value }"
			:disabled="node.fetching"
			@mouseover="onMouseover"
			@mouseleave="onMouseleave"
		>
			<div v-html="icon"></div>
			<a class="tree-label">{{ node.label }}</a>
			<!-- Icon open File record in new tab -->
			<a
				v-if="node.is_leaf"
				:href="open_file(node.value)"
				:disabled="node.fetching"
				target="_blank"
				class="file-doc-link ml-3"
			>
				<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 512 512">
					<!--! Font Awesome Free 6.4.2 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license (Commercial License) Copyright 2023 Fonticons, Inc. -->
					<path
						d="M320 0c-17.7 0-32 14.3-32 32s14.3 32 32 32h82.7L201.4 265.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L448 109.3V192c0 17.7 14.3 32 32 32s32-14.3 32-32V32c0-17.7-14.3-32-32-32H320zM80 32C35.8 32 0 67.8 0 112V432c0 44.2 35.8 80 80 80H400c44.2 0 80-35.8 80-80V320c0-17.7-14.3-32-32-32s-32 14.3-32 32V432c0 8.8-7.2 16-16 16H80c-8.8 0-16-7.2-16-16V112c0-8.8 7.2-16 16-16H192c17.7 0 32-14.3 32-32s-14.3-32-32-32H80z"
					/>
				</svg>
			</a>
		</span>
		<div v-if="node.file_url && frappe.utils.is_image_file(node.file_url)">
			<div v-show="isOpen" class="popover" ref="popover" role="tooltip">
				<img :src="node.file_url" />
			</div>
		</div>
		<ul class="tree-children" v-show="node.open">
			<TreeNode
				v-for="n in node.children"
				:key="n.value"
				:node="n"
				:selected_node="selected_node"
				@node-click="(n) => emit('node-click', n)"
				@load-more="(n) => emit('load-more', n)"
			/>
			<button
				class="btn btn-xs btn-load-more"
				v-if="node.has_more_children"
				@click="emit('load-more', node)"
				:disabled="node.children_loading"
			>
				{{ node.children_loading ? __("Loading...") : __("Load more") }}
			</button>
		</ul>
	</div>
</template>

<script setup>
import TreeNode from "./TreeNode.vue";
import { createPopper } from "@popperjs/core";
import { ref, computed } from "vue";

// props
const props = defineProps({
	node: Object,
	selected_node: Object,
});

// emits
let emit = defineEmits(["node-click", "load-more"]);

// computed

let icon = computed(() => {
	let icons = {
		open: frappe.utils.icon("folder-open", "md"),
		closed: frappe.utils.icon("folder-normal", "md"),
		leaf: frappe.utils.icon("primitive-dot", "xs"),
		search: frappe.utils.icon("search"),
	};

	if (props.node.by_search) return icons.search;
	if (props.node.is_leaf) return icons.leaf;
	if (props.node.open) return icons.open;
	return icons.closed;
});

let open_file = (filename) => {
	return frappe.utils.get_form_link("File", filename);
};

const reference = ref(null);
const popover = ref(null);
let isOpen = ref(false);

let popper = ref(null);

function setupPopper() {
	if (!popper.value) {
		popper.value = createPopper(reference.value, popover.value, {
			placement: "top",
			modifiers: [
				{
					name: "offset",
					options: {
						offset: [0, 4],
					},
				},
			],
		});
	} else {
		popper.value.update();
	}
}

let hoverTimer = null;
let leaveTimer = null;

function onMouseover() {
	leaveTimer && clearTimeout(leaveTimer) && (leaveTimer = null);
	hoverTimer && clearTimeout(hoverTimer);
	hoverTimer = setTimeout(() => {
		isOpen.value = true;
		setupPopper();
	}, 800);
}
function onMouseleave() {
	hoverTimer && clearTimeout(hoverTimer) && (hoverTimer = null);
	leaveTimer && clearTimeout(leaveTimer);
	leaveTimer = setTimeout(() => {
		isOpen.value = false;
	}, 100);
}
</script>

<style scoped>
.btn-load-more {
	margin-left: 1.6rem;
	margin-top: 0.5rem;
}
.popover {
	padding: 10px;
}
</style>
