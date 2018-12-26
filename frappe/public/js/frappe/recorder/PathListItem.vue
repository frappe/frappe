<template>
	<tr>
		<td>
			<a :href="'#Path/' + path ">{{ path }}</a>
		</td>
		<td>
			{{ count }}
		</td>
	</tr>
</template>

<script>
export default {
	name: "PathListItem",
	props: ["path", "count"]
};
</script>
