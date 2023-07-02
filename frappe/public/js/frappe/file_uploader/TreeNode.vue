<template>
	<div class="tree-node" :class="{ opened: node.open }">
		<span
			class="tree-link"
			@click="emit('node-click', node)"
			:class="{ active: node.value === selected_node.value }"
			:disabled="node.fetching"
		>
			<div v-html="icon"></div>
			<a class="tree-label">{{ node.label }}</a>
		</span>
		<ul class="tree-children" v-show="node.open">
			<TreeNode
				v-for="n in node.children"
				:key="n.value"
				:node="n"
				:selected_node="selected_node"
				@node-click="n => emit('node-click', n)"
				@load-more="n => emit('load-more', n)"
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
import { computed } from "vue";

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
		search: frappe.utils.icon("search")
	};

	if (props.node.by_search) return icons.search;
	if (props.node.is_leaf) return icons.leaf;
	if (props.node.open) return icons.open;
	return icons.closed;
});

</script>

<style scoped>
.btn-load-more {
	margin-left: 1.6rem;
	margin-top: 0.5rem;
}
</style>
