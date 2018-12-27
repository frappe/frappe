<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>UUID</th>
				<th>Path</th>
				<th>CMD</th>
			</tr>
		</thead>
		<tbody>
			<tr v-for="request in requests" :key="request.uuid" v-bind="request">
				<td>
					<a :href="'#Request/' + request.uuid ">{{ request.uuid }}</a>
				</td>
				<td>
					{{ request.path }}
				</td>
				<td>
					{{ request.cmd }}
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
			requests: [],
		};
	},
	mounted() {
		frappe.call("frappe.www.recorder.get_requests").then( r => {
			this.requests = r.message
		})
	},
};
</script>
