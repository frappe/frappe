<template>
	<div>
		<h1>
			<span>Recorder</span>
			<span class="indicator" :class="status.color">{{ status.status }}</span>
			<span class="chart-actions btn-group dropdown pull-right" style="float:right; margin-left:15px">
				<button v-if="status.status == 'Inactive'" class="btn btn-default btn-primary" @click="record(true)">Start</button>
				<button v-if="status.status == 'Active'" class="btn btn-default btn-primary" @click="record(false)">Stop</button>
			</span>
		</h1>
		<table class="table table-hover">
			<thead>
				<tr>
					<th><span style="margin-right:5px">Index</span><i @click="sort('index')" class="glyphicon" :class="glyphicon('index')"></i></th>
					<th><span style="margin-right:5px">Time</span><i @click="sort('time')" class="glyphicon" :class="glyphicon('time')"></i></th>
					<th><span style="margin-right:5px">Method</span><i @click="sort('method')" class="glyphicon" :class="glyphicon('method')"></i></th>
					<th><span style="margin-right:5px">Path</span><i @click="sort('path')" class="glyphicon" :class="glyphicon('path')"></i></th>
					<th><span style="margin-right:5px">CMD</span><i @click="sort('cmd')" class="glyphicon" :class="glyphicon('cmd')"></i></th>
				</tr>
			</thead>
			<tbody>
				<tr>
					<td></td>
					<td></td>
					<td><input v-model="query.filters.method"/></td>
					<td><input v-model="query.filters.path"/></td>
					<td><input v-model="query.filters.cmd"/></td>
				</tr>
				<router-link style="cursor: pointer" :to="{name: 'request-detail', params: {request_uuid: request.uuid}}" tag="tr"  v-for="request in paginated(sorted(filtered(requests)))" :key="request.index" v-bind="request">
					<td>{{ request.index }}</td>
					<td>{{ request.time }}</td>
					<td>{{ request.method }}</td>
					<td>{{ request.path | elipsize }}</td>
					<td>{{ request.cmd | elipsize }}</td>
				</router-link>
			</tbody>
		</table>
		<nav>
			<ul class="pagination">
				<li class="page-item" :class="query.pagination.limit == page ? 'active' : ''" v-for="(page, index) in [20, 100, 500]" :key="index">
					<a class="page-link" @click="query.pagination.limit = page">{{ page }}</a>
				</li>
			</ul>
			<ul class="pagination" style="float:right">
				<li class="page-item" :class="page.status" v-for="(page, index) in pages" :key="index">
					<a class="page-link" @click="query.pagination.page = page.number ">{{ page.label }}</a>
				</li>
			</ul>
		</nav>
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
					limit: 20,
					page: 1,
					total: 0,
				}
			},
			status: {
				color: "grey",
				status: "Unknown",
			},
			last_fetched: null,
		};
	},
	mounted() {
		frappe.socketio.init(9000);
		this.fetch_status();
		this.refresh();
	},
	computed: {
		pages: function() {
			const current_page = this.query.pagination.page;
			const total_pages = this.query.pagination.total;
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
			}];
		}
	},
	methods: {
		filtered: function(requests) {
			requests = requests.slice();
			const filters = Object.entries(this.query.filters);
			requests = requests.filter(
				(r) => filters.map((f) => (r[f[0]] || "").match(f[1])).every(Boolean)
			);
			this.query.pagination.total = Math.ceil(requests.length / this.query.pagination.limit);
			return requests;
		},
		paginated: function(requests) {
			requests = requests.slice();
			const begin = (this.query.pagination.page - 1) * (this.query.pagination.limit);
			const end = begin + this.query.pagination.limit;
			return requests.slice(begin, end);
		},
		sorted: function(requests) {
			requests = requests.slice();
			const order = (this.query.order == "asc") ? 1 : -1;
			const sort = this.query.sort;
			return requests.sort((a,b) => (a[sort] > b[sort]) ? order : -order);
		},
		sort: function(key) {
			if(key == this.query.sort) {
				this.query.order = (this.query.order == "asc") ? "desc" : "asc";
			} else {
				this.query.order = "asc";
			}
			this.query.sort = key;
		},
		glyphicon: function(key) {
			if(key == this.query.sort) {
				return (this.query.order == "asc") ? "glyphicon-sort-by-attributes" : "glyphicon-sort-by-attributes-alt";
			} else {
				return "glyphicon-sort";
			}
		},
		refresh: function() {
			frappe.call("frappe.www.recorder.get_requests").then( r => {
				this.requests = r.message;
				this.last_fetched = new Date();
			});
		},
		record: function(should_record) {
			frappe.call({
				method: "frappe.www.recorder.set_recorder_state",
				args: {
					should_record: should_record
				}
			}).then(r => this.update_status(r.message));
		},
		fetch_status: function() {
			frappe.call("frappe.www.recorder.get_status").then(r => this.update_status(r.message));
		},
		update_status: function(status) {
			this.status = status;
			if(this.status.status == "Active") {
				frappe.realtime.on("recorder-dump-event", this.refresh);
			} else {
				frappe.realtime.off("recorder-dump-event", this.refresh);
			}
		},
	},
	filters: {
		elipsize: function (value) {
			if (!value) return '';
			if (value.length > 30)
				return value.substring(0, 30-3)+'...';
			return value;
		}
	}
};
</script>
