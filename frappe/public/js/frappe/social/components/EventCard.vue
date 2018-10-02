<template>
	<div class="event-card">
		<div class="content" v-html="event.content"/>
	</div>
</template>
<script>
export default {
	props: ['event'],
}
</script>