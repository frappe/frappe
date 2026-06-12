<template>
	<div class="p-6 max-w-3xl space-y-8">
		<!-- ── Composition showcase ─────────────────────────────────────────────
		     The writer (`CodeEditor`) and preview (`CodePreview`) are two agnostic
		     primitives; how the preview is triggered is a composition choice. These
		     three blocks show the common ways — editor-only, Write/Preview toggle,
		     and side-by-side split — so the field wrapper's toggle is just one of
		     them, not baked into the primitive. -->

		<div>
			<div class="mb-2 flex items-center gap-3">
				<h3 class="text-xl-semibold text-ink-gray-9">Editor only</h3>
				<Select v-model="language" :options="languages" />
				<Select v-model="variant" :options="variants" />
			</div>
			<CodeEditor
				v-model="code"
				:language="language"
				:variant="variant"
				placeholder="Type some code…"
			/>
			<pre class="mt-3 text-xs text-ink-gray-6">value = {{ code }}</pre>
		</div>

		<div>
			<div class="mb-2 flex items-center gap-3">
				<h3 class="text-xl-semibold text-ink-gray-9">Write / Preview toggle</h3>
				<div class="flex gap-1">
					<Button
						:variant="mode === 'write' ? 'subtle' : 'ghost'"
						size="sm"
						label="Write"
						@click="mode = 'write'"
					/>
					<Button
						:variant="mode === 'preview' ? 'subtle' : 'ghost'"
						size="sm"
						label="Preview"
						@click="mode = 'preview'"
					/>
				</div>
			</div>
			<CodeEditor v-show="mode === 'write'" v-model="markdown" language="markdown" />
			<CodePreview
				v-if="mode === 'preview'"
				:modelValue="markdown"
				language="markdown"
				class="min-h-[4.5rem] rounded-md border border-surface-gray-2 p-3"
			/>
		</div>

		<div>
			<h3 class="mb-2 text-xl-semibold text-ink-gray-9">Side-by-side split</h3>
			<div class="grid grid-cols-2 gap-3">
				<CodeEditor v-model="htmlSrc" language="html" />
				<CodePreview
					:modelValue="htmlSrc"
					language="html"
					class="min-h-[4.5rem] rounded-md border border-surface-gray-2 p-3"
				/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button, Select } from "frappe-ui";
import CodeEditor from "../CodeEditor.vue";
import CodePreview from "../CodePreview.vue";
import type { CodeEditorVariant } from "../types";

const languages = [
	"plain",
	"json",
	"javascript",
	"python",
	"sql",
	"css",
	"scss",
	"html",
	"xml",
	"yaml",
	"markdown",
];
const language = ref("javascript");
const variants = ["subtle", "outline", "ghost"];
const variant = ref<CodeEditorVariant>("subtle");
const code = ref(`function greet(name) {\n\treturn \`Hello, \${name}!\`;\n}`);

const mode = ref<"write" | "preview">("write");
const markdown = ref(`# Notes\n\nSome **bold** text and a [link](https://frappe.io).`);

const htmlSrc = ref(`<h2>Title</h2>\n<p>Edit the HTML on the left.</p>`);
</script>
