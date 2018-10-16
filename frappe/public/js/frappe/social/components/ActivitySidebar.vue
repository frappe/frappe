<template>
	<div>
		<div class="muted-title">Upcoming Events</div>
		<div class="event" v-for="event in events" :key="event.name">
			<span class="bold">{{ get_time(event.starts_on) }}</span>
			<span> {{ event.subject }}</span>
		</div>
		<div class="muted-title">Chat</div>
		<a @click="open_chat">
			Open Chat
		</a>
	</div>
</template>
<script>
export default {
	data() {
		return {
			'events': []
		}
	},
	created() {
		this.get_events().then((events) => {
			this.events = events
		})
	},
	methods: {
		get_events() {
			const today = frappe.datetime.now_date();
			return frappe.xcall('frappe.desk.doctype.event.event.get_events', {
				start: today,
				end: today
			})
		},
		open_chat() {
			frappe.chat.widget.toggle();
		},
		get_time(timestamp) {
			return frappe.datetime.get_time(timestamp)
		},
	}
}
</script>
