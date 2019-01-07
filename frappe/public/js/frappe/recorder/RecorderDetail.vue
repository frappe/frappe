<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>Index<button v-on:click=" key='index'">Sort</button></th>
				<th>Time<button v-on:click=" key='time'">Sort</button></th>
				<th>Method<button v-on:click=" key='method'">Sort</button></th>
				<th>Path<button v-on:click=" key='path'">Sort</button></th>
				<th>CMD<button v-on:click=" key='cmd'">Sort</button></th>
			</tr>
		</thead>
		<tbody>
			<router-link style="cursor: pointer" :to="{name: 'request-detail', params: {request_uuid: request.uuid}}" tag="tr"  v-for="request in sortedRequests" :key="request.index" v-bind="request">
				<td>{{ request.index }}</td>
				<td>{{ request.time }}</td>
				<td>{{ request.method }}</td>
				<td>{{ request.path }}</td>
				<td>{{ request.cmd }}</td>
			</router-link>
		</tbody>
	</table>
</template>

<script>
export default {
	name: "RecorderDetail",
	data() {
		return {
			requests: [],
			key: "index",
		};
	},
	mounted() {
		frappe.call("frappe.www.recorder.get_requests").then( r => {
			this.requests = r.message
		})
	},
	computed: {
		sortedRequests: function() {
			return this.requests.sort((a,b) => (a[this.key] > b[this.key]) ? 1 : -1)
		}
	},
};
</script>
