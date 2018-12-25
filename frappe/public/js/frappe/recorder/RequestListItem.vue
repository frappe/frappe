<template>
	<a :href="'#Request/' + uuid ">
		<div>
			{{ uuid }} - {{ cmd }}
		</div>
	</a>
</template>

<script>
export default {
	name: "RequestListItem",
	props: ["uuid", "cmd"]
};
</script>
