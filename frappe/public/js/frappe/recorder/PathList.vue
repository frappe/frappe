<template>
	<div>
		<ol>
			<li v-for="path in paths" :key="path.path">
				<path-list-item v-bind="path"/>
			</li>
		</ol>
	</div>
</template>

<script>
import PathListItem from "./PathListItem.vue"
export default {
	name: "PathList",
	data() {
		return {
			paths: [],
		};
	},
	mounted() {
		frappe.call("frappe.www.recorder.get_paths").then( r => {
			this.paths = r.message
		})
	},
	components: {
		PathListItem,
	}
};
</script>
