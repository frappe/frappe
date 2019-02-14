<template>
	<div>
		<div class="frappe-list">
			<div class="list-filters"></div>
			<div style="margin-bottom:9px" class="list-toolbar-wrapper hide">
				<div class="list-toolbar btn-group" style="display:inline-block; margin-right: 10px;"></div>
			</div>
			<div style="clear:both"></div>
			<div class="filter-list">
				<div class="tag-filters-area">
					<div class="active-tag-filters">
						<button class="btn btn-default btn-xs add-filter text-muted">
							Add Filter
						</button>
					</div>
				</div>
				<div class="filter-edit-area"></div>
				<div class="sort-selector">
					<div class="dropdown"><a class="text-muted dropdown-toggle small" data-toggle="dropdown"><span class="dropdown-text">{{ columns.filter(c => c.slug == query.sort)[0].label }}</span></a>
						<ul class="dropdown-menu">
							<li v-for="(column, index) in columns.filter(c => c.sortable)" :key="index" @click="query.sort = column.slug"><a class="option">{{ column.label }}</a></li>
						</ul>
					</div>
					<button class="btn btn-default btn-xs btn-order">
						<span class="octicon text-muted" :class="query.order == 'asc' ? 'octicon-arrow-down' : 'octicon-arrow-up'"  @click="query.order = (query.order == 'asc') ? 'desc' : 'asc'"></span>
					</button>
				</div>
			</div>
			<div  v-if="requests.length != 0" class="result">
				<div class="list-headers">
					<header class="level list-row list-row-head text-muted small">
						<div class="level-left list-header-subject">
							<div class="list-row-col ellipsis list-subject level ">
								<span class="level-item">{{ columns[0].label }}</span>
							</div>
							<div class="list-row-col ellipsis hidden-xs"  v-for="(column, index) in columns.slice(1)" :key="index">
								<span>{{ column.label }}</span>
							</div>
						</div>
						<div class="level-right">
							<span class="list-count"><span>{{ (query.pagination.page - 1) * (query.pagination.limit) + 1 }} - {{ Math.min(query.pagination.page * query.pagination.limit, requests.length) }} of {{ requests.length }}</span></span>
						</div>
					</header>

				</div>
				<div class="result-list">
					<div class="list-row-container" v-for="request in paginated(sorted(filtered(requests)))" :key="request.index">
						<div class="level list-row small">
							<div class="level-left ellipsis">
								<div class="list-row-col ellipsis list-subject level ">
									<span class="level-item bold ellipsis">
										{{ request[columns[0].slug] }}
									</span>
								</div>
								<div class="list-row-col ellipsis" v-for="(column, index) in columns.slice(1)" :key="index">
									<span class="ellipsis text-muted">{{ request[column.slug] }}</span>
								</div>
							</div>
							<div class="level-right ellipsis">
								<div class="list-row-col ellipsis list-subject level ">
									<span class="level-item ellipsis text-muted">
										{{ request.path }}
									</span>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div v-if="requests.length == 0" class="no-result text-muted flex justify-center align-center" style="">
				<div class="msg-box no-border" v-if="status.status == 'Inactive'" >
					<p>Recorder is Inactive</p>
					<p><button class="btn btn-primary btn-sm btn-new-doc" @click="record(true)">Start Recording</button></p>
				</div>
				<div class="msg-box no-border" v-if="status.status == 'Active'" >
					<p>No Requests found</p>
					<p>Go make some noise</p>
				</div>
			</div>
			<div v-if="requests.length != 0" class="list-paging-area">
				<div class="row">
					<div class="col-xs-6">
						<div class="btn-group btn-group-paging">
							<button type="button" class="btn btn-default btn-sm" v-for="(limit, index) in [20, 100, 500]" :key="index" :class="query.pagination.limit == limit ? 'btn-info' : ''" @click="query.pagination.limit = limit">
								{{ limit }}
							</button>
						</div>
					</div>
					<div class="col-xs-6 text-right">
						<div class="btn-group btn-group-paging">
							<button type="button" class="btn btn-default btn-sm" :class="page.status" v-for="(page, index) in pages" :key="index" @click="query.pagination.page = page.number">
								{{ page.label }}
							</button>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script>
export default {
	name: "RecorderDetail",
	data() {
		return {
			requests: [],
			columns: [
				{label: "Time", slug: "time", sortable: true},
				{label: "Duration", slug: "duration", sortable: true},
				{label: "Time in Queries", slug: "time_queries", sortable: true},
				{label: "Queries", slug: "queries", sortable: true},
				{label: "Method", slug: "method"},

			],
			query: {
				sort: "time",
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
		this.$root.page.set_secondary_action("Clear", () => {
			this.clear();
		});

	},
	computed: {
		pages: function() {
			const current_page = this.query.pagination.page;
			const total_pages = this.query.pagination.total;
			return [{
				label: "First",
				number: 1,
				status: (current_page == 1) ? "disabled" : "",
			},{
				label: "Previous",
				number: Math.max(current_page - 1, 1),
				status: (current_page == 1) ? "disabled" : "",
			}, {
				label: current_page,
				number: current_page,
				status: "btn-info",
			}, {
				label: "Next",
				number: Math.min(current_page + 1, total_pages),
				status: (current_page == total_pages) ? "disabled" : "",
			}, {
				label: "Last",
				number: total_pages,
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
		clear: function() {
			frappe.call("frappe.www.recorder.erase_requests");
			this.refresh();
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
			this.$root.page.set_indicator(this.status.status, this.status.color);
			if(this.status.status == "Active") {
				frappe.realtime.on("recorder-dump-event", this.refresh);
			} else {
				frappe.realtime.off("recorder-dump-event", this.refresh);
			}

			this.update_buttons();
		},
		update_buttons: function() {
			if(this.status.status == "Active") {
				this.$root.page.set_primary_action("Stop", () => {
					this.record(false);
				});
			} else {
				this.$root.page.set_primary_action("Start", () => {
					this.record(true);
				});
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
