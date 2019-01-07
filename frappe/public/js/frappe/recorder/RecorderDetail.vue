<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>Index<button @click=" sort('index') ">Sort</button></th>
				<th>Time<button @click=" sort('time') ">Sort</button></th>
				<th>Method<button @click=" sort('method') ">Sort</button></th>
				<th>Path<button @click=" sort('path') ">Sort</button></th>
				<th>CMD<button @click=" sort('cmd') ">Sort</button></th>
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
			query: {
				sort: "index",
				order: "asc",
			},
		};
	},
	mounted() {
		frappe.call("frappe.www.recorder.get_requests").then( r => {
			this.requests = r.message
		})
	},
	computed: {
		sortedRequests: function() {
			const order = (this.query.order == "asc") ? 1 : -1
			const sort = this.query.sort
			return this.requests.sort((a,b) => (a[sort] > b[sort]) ? order : -order)
		}
	},
	methods: {
		sort: function(key) {
			if(key == this.query.sort) {
				this.query.order = (this.query.order == "asc") ? "desc" : "asc"
			}
			else {
				this.query.order = "asc"
			}
			this.query.sort = key
		}
	}
};
</script>
