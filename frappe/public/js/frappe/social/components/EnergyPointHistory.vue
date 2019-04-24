<template>
	<div>
		<ul class="log-list">
			<li class="history-log" v-for="log in history_logs" :key="log.name">
				<span v-html="frappe.energy_points.format_history_log(log, true)"></span>
			</li>
			<li v-if="fetching" class="history-log">
				{{ __('Fetching') + '...' }}
			</li>
			<li v-else-if="has_more_logs" class="history-log">
				<button
					class="btn btn-default btn-xs"
					@click="get_logs()">
					{{ __('Load more') }}
				</button>
			</li>
			<li v-else-if="!history_logs.length" class="history-log">
				{{ __('No logs found') }}
			</li>
		</ul>
	</div>
</template>
<script>
export default {
	props: ['user', 'from_date'],
	data() {
		return {
			history_logs: [],
			fetching: false,
			has_more_logs: true
		};
	},
	created() {
		this.get_logs();
	},
	methods: {
		get_logs() {
			this.fetching = true;
			const pull_limit = 10;
			frappe.db
				.get_list('Energy Point Log', {
					filters: {
						user: this.user,
						type: ['!=', 'Review'],
						creation: ['>=',  this.from_date]
					},
					fields: ['*'],
					limit: pull_limit,
					limit_start: this.history_logs.length
				})
				.then(data => {
					this.history_logs = this.history_logs.concat(data);
					this.has_more_logs = data.length === pull_limit;
				})
				.finally(() => {
					this.fetching = false;
				});
		}
	}
};
</script>
<style lang="less">
@import 'frappe/public/less/common';
.log-list {
	padding: 15px;
	padding-left: 0px;
	position: relative;
}
.log-list:before {
	content: ' ';
	border-left: 1px solid @border-color;
	position: absolute;
	top: 0px;
	bottom: 0px;
	left: 30px;
	z-index: 0;
}
.history-log {
	.text-muted;
	.text-medium;
	list-style: none;
	padding: 10px;
	padding-left: 50px;
	display: flex;
	position: relative;
}
.history-log:before {
	content: ' ';
	width: 7px;
	height: 7px;
	background-color: @border-color;
	position: absolute;
	border-radius: 50%;
	left: 27px;
	top: 16px;
}
</style>