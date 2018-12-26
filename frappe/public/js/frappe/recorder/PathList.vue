<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>Path</th>
				<th>Count</th>
			</tr>
		</thead>
		<tbody>
			<path-list-item v-for="path in paths" :key="path.path" v-bind="path"/>
		</tbody>
	</table>
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
