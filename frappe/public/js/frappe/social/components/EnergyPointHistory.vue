<template>
	<div>
		<ul class="log-list">
			<li class="history-log" v-for="log in history_logs" :key="log.name">
				<span v-html="frappe.utils.get_points(log.points)"></span>
				<span v-html="log_body(log)"></span>
				<span>&nbsp;-&nbsp;</span>
				<span v-html="frappe.datetime.comment_when(log.creation)"></span>
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
	methods: {
		log_body(log) {
			const doc_link = frappe.utils.get_form_link(log.reference_doctype, log.reference_name, true)
			const owner_name = frappe.user.full_name(log.owner).bold();
			if (log.type === 'Appreciation') {
				return __('{0} appreciated on {1}', [owner_name, doc_link])
			}
			if (log.type === 'Criticism') {
				return __('{0} criticized on {1}', [owner_name, doc_link])
			}
			return __('via automatic rule {0} for {1}', [log.rule.bold(), doc_link])
		}
	}

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
	span:nth-child(1) {
		width: 40px;
		text-align: right;
		margin-right: 10px;
	}
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