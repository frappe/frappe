<template>
	<div class="file-web-link margin-bottom">
		<a href class="back-link text-muted text-medium"
			@click.prevent="$emit('hide-web-link')"
		>
			{{ __('← Back to upload files') }}
		</a>
		<div class="form-group">
			<label>
				<div class="control-label">
					{{ __('Web Link') }}
				</div>
				<input
					type="text"
					class="form-control"
					v-model="url"
				>
			</label>
		</div>
		<div class="form-group">
			<label>
				<div class="control-label">
					{{ __('Link Name (Optional)') }}
				</div>
				<input
					type="text"
					class="form-control"
					v-model="name"
				>
			</label>
		</div>
	</div>
</template>
<script>
export default {
	name: 'WebLink',
	data() {
		return {
			url: '',
			name: ''
		}
	}
}
</script>

<style scoped>
.form-group label {
	width: 100%;
}

.form-group .form-control {
	font-weight: normal;
}

.back-link {
	display: block;
	margin-bottom: 15px;
}
</style>
