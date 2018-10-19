<template>
	<div>
		{{ path }} {{ count }}
	</div>
</template>

<script>
export default {
	name: "PathListItem",
	props: ["path", "count"]
};
</script>
