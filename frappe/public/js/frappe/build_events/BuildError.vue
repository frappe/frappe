<template>
	<div class="build-error-overlay" @click.self="data = null" v-show="data">
		<div class="window" v-if="data">
			<div v-for="(error, i) in data.formatted" :key="i">
				<!-- prettier-ignore -->
				<pre class="frame"><component :is="error_component(error, i)" /></pre>
			</div>
			<pre class="stack">{{ data.stack }}</pre>
		</div>
	</div>
</template>
<script>
export default {
	name: "BuildError",
	data() {
		return {
			data: null,
		};
	},
	methods: {
		show(data) {
			this.data = data;
		},
		hide() {
			this.data = null;
		},
		open_in_editor(location) {
			frappe.socketio.socket.emit("open_in_editor", location);
		},
		error_component(error, i) {
			let location = this.data.error.errors[i].location;
			let location_string = `${location.file}:${location.line}:${location.column}`;
			let template = error.replace(
				" > " + location_string,
				` &gt; <a class="file-link" @click="open">${location_string}</a>`
			);

			return {
				template: `<div>${template}</div>`,
				methods: {
					open() {
						frappe.socketio.socket.emit("open_in_editor", location);
					},
				},
			};
		},
	},
};
</script>
<style>
.build-error-overlay {
	position: fixed;
	top: 0;
	left: 0;
	width: 100%;
	height: 100%;
	z-index: 9999;
	margin: 0;
	background: rgba(0, 0, 0, 0.66);
	--monospace: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
	--dim: var(--gray-400);
}
.window {
	font-family: var(--monospace);
	line-height: 1.5;
	width: 800px;
	color: #d8d8d8;
	margin: 30px auto;
	padding: 25px 40px;
	position: relative;
	background: #181818;
	border-radius: 6px 6px 8px 8px;
	box-shadow: 0 19px 38px rgba(0, 0, 0, 0.3), 0 15px 12px rgba(0, 0, 0, 0.22);
	overflow: hidden;
	border-top: 8px solid var(--red);
}

pre {
	font-family: var(--monospace);
	font-size: 13px;
	margin-top: 0;
	margin-bottom: 1em;
	overflow-x: auto;
	scrollbar-width: none;
}
code {
	font-size: 13px;
	font-family: var(--monospace);
	color: var(--yellow);
}

.message {
	line-height: 1.3;
	font-weight: 600;
	white-space: pre-wrap;
}
.frame {
	color: var(--yellow);
}
.stack {
	font-size: 13px;
	color: var(--dim);
}
.file-link {
	text-decoration: underline !important;
	cursor: pointer;
}
</style>
