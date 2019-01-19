<template>
	<table class="table table-hover table-condensed">
		<thead>
			<tr>
				<th style="width:8%"><span style="margin-right:5px">Index</span><i @click="sort('index')" class="glyphicon" :class="glyphicon('index')"></i></th>
				<th style="width:82%"><span>Query</span></th>
				<th style="width:10%"><span style="margin-right:5px">Duration</span><i @click="sort('duration')" class="glyphicon" :class="glyphicon('duration')"></i></th>
			</tr>
		</thead>
		<tbody>
			<tr>
				<td></td>
				<td><input style="width:100%" v-model="query.filters.query"/></td>
				<td></td>
			</tr>
			<router-link style="cursor: pointer" :to="{name: 'sql-detail', params: {call_index: call.index}}" tag="tr" v-for="call in sorted(filtered(calls))" :key="call.index" v-bind="call">
				<td>{{ call.index }}</td>
				<td>{{ call.query }}</td>
				<td>{{ call.duration }}</td>
			</router-link>
		</tbody>
	</table>

</template>

<script>
export default {
	name: "RequestDetail",
 	data() {
		return {
			calls: [],
			query: {
				sort: "index",
				order: "asc",
				filters: {},
			},
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_request_data",
			args: {
				uuid: this.$route.params.request_uuid
			}
		}).then( r => {
			this.calls = r.message.calls;
		});
	},
	methods: {
		filtered: function(calls) {
			calls = calls.slice();
			const filters = Object.entries(this.query.filters);
			calls = calls.filter(
				(r) => filters.map((f) => (r[f[0]] || "").match(f[1])).every(Boolean)
			);
			return calls;
		},
		sorted: function(calls) {
			calls = calls.slice();
			const order = (this.query.order == "asc") ? 1 : -1;
			const sort = this.query.sort;
			return calls.sort((a,b) => (a[sort] > b[sort]) ? order : -order);
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
	}
};
</script>
