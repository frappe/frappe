<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>UUID</th>
				<th>Path</th>
				<th>CMD</th>
				<th>Time</th>
				<th>Method</th>
			</tr>
		</thead>
		<tbody>
			<tr v-for="request in requests" :key="request.uuid" v-bind="request">
				<td>
					<router-link :to="{name: 'request-detail', params: {request_uuid: request.uuid}} ">{{ request.uuid }}</router-link>
				</td>
				<td>
					{{ request.path }}
				</td>
				<td>
					{{ request.cmd }}
				</td>
				<td>
					{{ request.time }}
				</td>
				<td>
					{{ request.method }}
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
