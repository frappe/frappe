<template>
	<div>
		<h1>
			<span>Recorder</span>
			<span class="indicator" :class="status.color">{{ status.label }}</span>
		</h1>
		<table class="table table-hover">
			<thead>
				<tr>
					<th>Index<button @click=" sort('index') ">Sort</button></th>
					<th>Time<button @click=" sort('time') ">Sort</button></th>
					<th>Method<button @click=" sort('method') ">Sort</button><input v-model="query.filters.method"/></th>
					<th>Path<button @click=" sort('path') ">Sort</button><input v-model="query.filters.path"/></th>
					<th>CMD<button @click=" sort('cmd') ">Sort</button><input v-model="query.filters.cmd"/></th>
				</tr>
			</thead>
			<tbody>
				<router-link style="cursor: pointer" :to="{name: 'request-detail', params: {request_uuid: request.uuid}}" tag="tr"  v-for="request in paginated(sorted(filtered(requests)))" :key="request.index" v-bind="request">
					<td>{{ request.index }}</td>
					<td>{{ request.time }}</td>
					<td>{{ request.method }}</td>
					<td>{{ request.path }}</td>
					<td>{{ request.cmd }}</td>
				</router-link>
			</tbody>
		</table>
		<nav>
			<ul class="pagination">
				<li class="page-item" :class="page.status" v-for="(page, index) in pages" :key="index">
					<a class="page-link" @click="query.pagination.page = page.number ">{{ page.label }}</a>
				</li>
			</ul>
		</nav>
		<select class="custom-select" v-model="query.pagination.limit">
			<option value="10">10</option>
			<option value="20">20</option>
			<option value="50">50</option>
			<option value="100">100	</option>
		</select>
	</div>
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
				filters: {},
				pagination: {
					limit: 10,
					page: 1,
					total: 0,
				}
			},
			status: {
				color: "grey",
				label: "Unknown",
			}
		};
	},
	mounted() {
		frappe.call("frappe.www.recorder.get_status").then( r => {
			this.status = r.message
		})
		frappe.call("frappe.www.recorder.get_requests").then( r => {
			this.requests = r.message
		})
	},
	computed: {
		pages: function() {
			const current_page = this.query.pagination.page
			const total_pages = this.query.pagination.total
			return [{
				label:"Previous",
				number: Math.max(current_page - 1, 1),
				status: (current_page == 1) ? "disabled" : "",
			}, {
				label: current_page,
				number: current_page,
				status: "active",
			}, {
				label:"Next",
				number: Math.min(current_page + 1, total_pages),
				status: (current_page == total_pages) ? "disabled" : "",
			}]
		}
	},
	methods: {
		filtered: function(requests) {
			requests = requests.slice()
			const filters = Object.entries(this.query.filters)
			requests = requests.filter(
				(r) => filters.map((f) => (r[f[0]] || "").match(f[1])).every(Boolean)
			)
			this.query.pagination.total = Math.ceil(requests.length / this.query.pagination.limit)
			return requests
		},
		paginated: function(requests) {
			requests = requests.slice()
			const begin = (this.query.pagination.page - 1) * (this.query.pagination.limit)
			const end = begin + this.query.pagination.limit
			return requests.slice(begin, end)
		},
		sorted: function(requests) {
			requests = requests.slice()
			const order = (this.query.order == "asc") ? 1 : -1
			const sort = this.query.sort
			return requests.sort((a,b) => (a[sort] > b[sort]) ? order : -order)
		},
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
