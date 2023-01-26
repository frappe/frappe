<template>
	<div v-cloak @drop.prevent="import_data" @dragover.prevent>
		<div class="page-form">
			<div class="filter-list">
				<div class="tag-filters-area">
					<div class="active-tag-filters">
						<button class="btn btn-default btn-xs add-filter text-muted">
							{{ __("Add Filter") }}
						</button>
					</div>
				</div>
				<div class="filter-edit-area"></div>
				<div class="sort-selector">
					<div class="dropdown">
						<a class="text-muted dropdown-toggle small" data-toggle="dropdown">
							<span class="dropdown-text">
								{{ columns.filter(c => c.slug == query.sort)[0].label }}
							</span>
						</a>
						<ul class="dropdown-menu">
							<li v-for="(column, index) in columns.filter(c => c.sortable)" :key="index" @click="query.sort = column.slug">
								<a class="option">
									{{ column.label }}
								</a>
							</li>
						</ul>
					</div>
					<button class="btn btn-default btn-xs btn-order">
						<span class="octicon text-muted" :class="query.order == 'asc' ? 'octicon-arrow-down' : 'octicon-arrow-up'"  @click="query.order = (query.order == 'asc') ? 'desc' : 'asc'"></span>
					</button>
				</div>
			</div>
		</div>
		<div class="frappe-list">
			<div class="list-filters"></div>
			<div style="margin-bottom:9px" class="list-toolbar-wrapper hide">
				<div class="list-toolbar btn-group" style="display:inline-block; margin-right: 10px;"></div>
			</div>
			<div style="clear:both"></div>
			<div  v-if="requests.length != 0" class="result">
				<div class="list-headers">
					<header class="level list-row list-row-head text-muted small">
						<div class="level-left list-header-subject">
							<div class="list-row-col ellipsis list-subject level ">
								<span class="level-item">{{ columns[0].label }}</span>
							</div>
							<div class="list-row-col ellipsis hidden-xs"  v-for="(column, index) in columns.slice(1)" :key="index" :class="{'text-right': column.number}">
								<span>{{ column.label }}</span>
							</div>
						</div>
						<div class="level-right">
							<span class="list-count"><span>{{ (query.pagination.page - 1) * (query.pagination.limit) + 1 }} - {{ Math.min(query.pagination.page * query.pagination.limit, requests.length) }} of {{ requests.length }}</span></span>
						</div>
					</header>

				</div>
				<div class="result-list">
					<div class="list-row-container" v-for="(request, index) in paginated(sorted(filtered(requests)))" :key="index" @click="route_to_request_detail(request)">
						<div class="level list-row small">
							<div class="level-left ellipsis">
								<div class="list-row-col ellipsis list-subject level ">
									<span class="level-item bold" :title="request[columns[0].slug]">
										{{ request[columns[0].slug] }}
									</span>
								</div>
								<div class="list-row-col ellipsis" v-for="(column, index) in columns.slice(1)" :key="index" :class="{'text-right': column.number}">
									<span class="ellipsis text-muted">{{ request[column.slug] }}</span>
								</div>
							</div>
							<div class="level-right ellipsis">
								<div class="list-row-col ellipsis list-subject level ">
									<span class="level-item ellipsis text-muted">

									</span>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div v-if="requests.length == 0" class="no-result text-muted flex justify-center align-center" style="">
				<div class="msg-box no-border" v-if="status.status == 'Inactive'" >
					<p>
						<button class="btn btn-primary btn-sm btn-new-doc" @click="start()">
							{{ __("Start Recording") }}
						</button>
					</p>
					<p>{{ __("Recorder is Inactive.") }}</p>
					<p>{{ __("Start recording or drag & drop a previously exported data file to view it.") }}</p>
				</div>
				<div class="msg-box no-border" v-if="status.status == 'Active'" >
					<p>{{ __("No Requests found") }}</p>
					<p>{{ __("Go make some noise") }}</p>
				</div>
			</div>
			<div v-else class="list-paging-area">
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

<script setup>
import { ref, computed, onMounted } from "vue"
import { useRouter } from "vue-router"

// variables
let router = ref(useRouter());
let requests = ref([]);
let page = frappe.pages["recorder"].page;

let columns = [
	{label: __("Path"), slug: "path"},
	{label: __("Duration (ms)"), slug: "duration", sortable: true, number: true},
	{label: __("Time in Queries (ms)"), slug: "time_queries", sortable: true, number: true},
	{label: __("Queries"), slug: "queries", sortable: true, number: true},
	{label: __("Method"), slug: "method"},
	{label: __("Time"), slug: "time", sortable: true},
];

let query = ref({
	sort: "duration",
	order: "desc",
	filters: {},
	pagination: {
		limit: 20,
		page: 1,
		total: 0,
	}
});

let status = ref({
	color: "grey",
	status: "Unknown",
});

// Started
frappe.recorder.router = router.value;
let route = frappe.get_route();
if (route[2]) {
	router.value.push({name: "RequestDetail", params: {id: route[2]}});
}

// Methods
function filtered(reqs) {
	reqs = reqs.slice();
	const filters = Object.entries(query.value.filters);
	reqs = reqs.filter(
		(r) => filters.map((f) => (r[f[0]] || "").match(f[1])).every(Boolean)
	);
	query.value.pagination.total = Math.ceil(reqs.length / query.value.pagination.limit);
	return reqs;
}
function paginated(reqs) {
	reqs = reqs.slice();
	const begin = (query.value.pagination.page - 1) * (query.value.pagination.limit);
	const end = begin + query.value.pagination.limit;
	return reqs.slice(begin, end);
}
function sorted(reqs) {
	reqs = reqs.slice();
	const order = (query.value.order == "asc") ? 1 : -1;
	const sort = query.value.sort;
	return reqs.sort((a,b) => (a[sort] > b[sort]) ? order : -order);
}
function refresh() {
	frappe.call("frappe.recorder.get").then( r => requests.value = r.message);
}
function update(message) {
	requests.value.push(JSON.parse(message));
}
function clear() {
	frappe.call("frappe.recorder.delete").then(r => refresh());
}
function start() {
	frappe.call("frappe.recorder.start").then(r => fetch_status());
}
function stop() {
	frappe.call("frappe.recorder.stop").then(r => fetch_status());
}
function fetch_status() {
	frappe.call("frappe.recorder.status").then(r => update_status(r.message));
}
function update_status(result) {
	if(result) {
		status.value = {status: "Active", color: "green"}
	} else {
		status.value = {status: "Inactive", color: "red"}
	}
	page.set_indicator(status.value.status, status.value.color);
	if(status.value.status == "Active") {
		frappe.realtime.on("recorder-dump-event", update);
	} else {
		frappe.realtime.off("recorder-dump-event", update);
	}

	update_buttons();
}
function update_buttons() {
	if(status.value.status == "Active") {
		page.set_primary_action(__("Stop"), () => {
			stop();
		});
	} else {
		page.set_primary_action(__("Start"), () => {
			start();
		});
	}
}
function route_to_request_detail(request) {
	router.value.beforeEach(async to => {
		if (to.meta.shouldFetch) {
			to.meta.request = await request
		}
	});
	router.value.push({name: "RequestDetail", params: {id: request.uuid}});
}
function export_data() {
	if (!requests.value) {
		return;
	}
	frappe.call("frappe.recorder.export_data")
		.then((r) => {
			const data = r.message;
			const filename = `${data[0]["uuid"]}..${data[data.length -1]["uuid"]}.json`

			const el = document.createElement("a");
			el.setAttribute("href", "data:application/json," + encodeURIComponent(JSON.stringify(data)));
			el.setAttribute("download", filename);
			el.click();
		});
}
function import_data(e) {
	if (requests.value.length > 0) {
		// don't replace existing capture
		return;
	}
	const request_file = e.dataTransfer.files[0];

	const file_reader = new FileReader();
	file_reader.readAsText(request_file, "UTF-8");
	file_reader.onload = ({target: {result}}) => {
		requests.value = JSON.parse(result);
	}
}

// Mounted
onMounted(() => {
	fetch_status();
	refresh();
	page.set_secondary_action(__("Clear"), () => {
		frappe.set_route("recorder");
		clear();
	});
	page.add_menu_item("Export data", () => export_data());
});

// Computed
let pages = computed(() => {
	const current_page = query.value.pagination.page;
	const total_pages = query.value.pagination.total;
	return [{
		label: __("First"),
		number: 1,
		status: (current_page == 1) ? "disabled" : "",
	},{
		label: __("Previous"),
		number: Math.max(current_page - 1, 1),
		status: (current_page == 1) ? "disabled" : "",
	}, {
		label: current_page,
		number: current_page,
		status: "btn-info",
	}, {
		label: __("Next"),
		number: Math.min(current_page + 1, total_pages),
		status: (current_page == total_pages) ? "disabled" : "",
	}, {
		label: __("Last"),
		number: total_pages,
		status: (current_page == total_pages) ? "disabled" : "",
	}];
});
</script>

<style scoped>
	.list-row .level-left {
		flex: 8;
		width: 100%;
	}
</style>
