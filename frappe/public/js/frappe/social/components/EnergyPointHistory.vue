<template>
	<div>
		<ul class="log-list">
			<li class="history-log" v-for="log in history_logs" :key="log.name">
				<span v-html="frappe.energy_points.format_log(log, true)"></span>
			</li>
			<li v-if="!history_logs.length" class="history-log">
				{{__('No logs found')}}
			</li>
		</ul>
	</div>
</template>
<script>
export default {
	props: ['user'],
	data() {
		return {
			history_logs: []
		}
	},
	created() {
		frappe.db.get_list('Energy Point Log', {
			filters: {
				user: this.user,
				type: ['!=', 'Review']
			},
			fields: ['*']
		}).then(data => {
			this.history_logs = data;
		})
	},

}
</script>
<style lang="less">
@import "frappe/public/less/common";
.log-list {
	padding: 15px;
	padding-left: 0px;
	position: relative;
}
.log-list:before {
	content: " ";
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
	content: " ";
	width: 7px;
	height: 7px;
	background-color: @border-color;
	position: absolute;
	border-radius: 50%;
	left: 27px;
	top: 16px;
}
</style>