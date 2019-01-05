<template>
	<div>
		<div>{{ call.time.start }}</div>
		<div>{{ call.time.end }}</div>
		<div>{{ call.time.total }}</div>
		<div v-html="call.highlighted_query"></div>
		<table class="table table-striped">
			<thead>
				<tr>
					<th v-for="(key, index) in call.explain_result.keys" :key="index" v-bind="call">{{ key }}</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="(row, index) in call.explain_result.values" :key="index" v-bind="call">
					<td v-for="(value, index) in row" :key="index" v-bind="call">{{ value }}</td>
				</tr>
			</tbody>
		</table>
		<table class="table table-striped">
			<thead>
				<tr>
					<th v-for="(key, index) in call.profile_result.keys" :key="index" v-bind="call">{{ key }}</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="(row, index) in call.profile_result.values" :key="index" v-bind="call">
					<td v-for="(value, index) in row" :key="index" v-bind="call">{{ value }}</td>
				</tr>
			</tbody>
		</table>
		<table class="table table-striped" >
			<thead>
				<tr>
					<th v-for="(key, index) in call.result.keys" :key="index" v-bind="call">{{ key }}</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="(row, index) in call.result.values" :key="index" v-bind="call">
					<td v-for="(value, index) in row" :key="index" v-bind="call">{{ value }}</td>
				</tr>
			</tbody>
		</table>
		<div><pre>{{ call.stack }}</pre></div>
	</div>
</template>

<script>
export default {
	name: "SQLDetail",
 	data() {
		return {
			call: null,
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_request_data",
			args: {
				uuid: this.$route.params.request_uuid
			}
		}).then( r => {
			this.call = r.message.calls[this.$route.params.call_index]
		})
	},
};
</script>
