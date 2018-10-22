<template>
	<a :href="'#Request/' + uuid ">
		<div>
			{{ uuid }}
		</div>
	</a>
</template>

<script>
export default {
	name: "RequestListItem",
	props: ["uuid"]
};
</script>
