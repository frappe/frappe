<template>
	<div>
		<div v-for="reply in replies" :key="reply.name">
			<post :post='reply'></post>
		</div>
	</div>
</template>
<script>

export default {
	props: ['replies'],
	components: {
		Post: () => Promise.resolve(frappe.social.Post)
	}
}
</script>
