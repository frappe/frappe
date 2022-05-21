<template>
	<div class="file-web-link margin-bottom">
		<a href class="text-muted text-medium"
			@click.prevent="$emit('hide-web-link')"
		>
			{{ __('← Back to upload files') }}
		</a>
		<div class="input-group">
			<input
				type="text"
				class="form-control"
				:placeholder="__('Attach a web link')"
				v-model="url"
			>
		</div>
		<div class="input-group">
			<input
				type="text"
				class="form-control"
				:placeholder="__('File Name')"
				v-model="url_title"
			>
		</div>
	</div>
</template>
<script>
export default {
	name: 'WebLink',
	data() {
		return {
			url: '',
			url_title: ''
		}
	}
}
</script>

<style>
.file-web-link .input-group {
	margin-top: 10px;
}
</style>
