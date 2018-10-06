<template>
	<div class="event-card">
		<div class="pull-right text-muted" v-html="event_time"></div>
		<div class="content" v-html="event.content"/>
	</div>
</template>
<script>
export default {
	props: ['event'],
	data() {
		return {
			event_time: comment_when(this.event.creation),
		}
	}
}
</script>
