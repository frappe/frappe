<template>
	<tr>
		<td>
			<a :href="'#Request/' + uuid ">{{ uuid }}</a>
		</td>
		<td>
			{{ cmd }}
		</td>
	</tr>
</template>

<script>
export default {
	name: "RequestListItem",
	props: ["uuid", "cmd"]
};
</script>
