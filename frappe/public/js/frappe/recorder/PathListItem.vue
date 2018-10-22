<template>
	<a :href="'#Path/' + path ">
		<div>
			{{ path }} {{ count }}
		</div>
	</a>
</template>

<script>
export default {
	name: "PathListItem",
	props: ["path", "count"]
};
</script>
