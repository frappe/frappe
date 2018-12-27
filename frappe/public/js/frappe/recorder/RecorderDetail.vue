<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>Path</th>
				<th>Count</th>
			</tr>
		</thead>
		<tbody>
			<tr v-for="path in paths" :key="path.path" v-bind="path">
				<td>
					<a :href="'#Path/' + path.path ">{{ path.path }}</a>
				</td>
				<td>
					{{ path.count }}
				</td>
			</tr>
		</tbody>
	</table>
</template>

<script>
export default {
	name: "RecorderDetail",
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
};
</script>
