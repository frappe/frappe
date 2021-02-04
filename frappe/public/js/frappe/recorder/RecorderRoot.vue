<template>
	<keep-alive include="RecorderDetail">
		<router-view/>
	</keep-alive>
</template>

<script>
export default {
	name: "RecorderRoot",
	created() {
		this.$router.push({name: 'recorder-detail'});
	},
};
</script>
