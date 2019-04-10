<template>
	<div class="tree-node" :class="{'opened': node.open}" v-show="node.filtered">
		<span
			class="tree-link"
			@click="$emit('node-click', node)"
			:class="{'active': node.value === selected_node.value}"
			:disabled="node.fetching"
		>
			<i v-if="node.is_leaf" class="octicon octicon-primitive-dot node-leaf"></i>
			<i v-else class="fa fa-fw node-parent" :class="[node.open ? 'fa-folder-open' : 'fa-folder']"></i>
			<a class="tree-label grey h6">{{ node.label }}</a>
		</span>
		<ul class="tree-children" v-show="node.open">
			<TreeNode
				v-for="n in node.children"
				:key="n.value"
				:node="n"
				:selected_node="selected_node"
				@node-click="n => $emit('node-click', n)"
			/>
		</ul>
	</div>
</template>
<script>
export default {
	name: 'TreeNode',
	props: ['node', 'selected_node'],
	components: {
		TreeNode: () => frappe.ui.components.TreeNode
	}
}
</script>
