<template>
	<!--
    frappe-ui POC island.

    Mount/portal/router/theme plumbing lives in `mountVueIsland`
    (frappe/public/js/frappe/ui/vue_island.js). The mount root carries
    `data-frappe-ui` + `data-theme="light"`, so this component just
    starts with its own padding/layout wrapper.

    All frappe-ui components are imported from the main `frappe-ui`
    entry; esbuild compiles them from source via the lucide-icons +
    Vue plugins in `esbuild/esbuild.js`.
  -->
	<div class="frappe-ui-poc-island p-6">
		<div class="mb-6">
			<h2 class="text-2xl font-semibold text-ink-gray-9 mb-1">
				frappe-ui Components in Desk
			</h2>
			<p class="text-p-base text-ink-gray-7">
				This page demonstrates frappe-ui Button and Dialog components running inside a
				Frappe Desk page as a lazy-loaded Vue island.
			</p>
		</div>

		<div class="flex gap-3 flex-wrap">
			<Button variant="solid" @click="basicDialogOpen = true"> Open Basic Dialog </Button>

			<Button variant="outline" @click="formDialogOpen = true"> Open Form Dialog </Button>

			<Button variant="ghost" theme="red" @click="confirmDialogOpen = true">
				Open Confirm Dialog
			</Button>
		</div>

		<!-- Basic Dialog -->
		<Dialog v-model="basicDialogOpen" :options="{ title: 'Hello from frappe-ui!' }">
			<template #body-content>
				<p class="text-p-base text-ink-gray-7">
					This Dialog is rendered by the <strong>frappe-ui</strong> library compiled as a
					pre-built desk entry. It runs on the same Vue 3 runtime as Workflow Builder and
					Form Builder, consuming the local
					<code class="bg-surface-gray-2 px-1 rounded text-sm font-mono">frappe-ui</code>
					package declared in Frappe's
					<code class="bg-surface-gray-2 px-1 rounded text-sm font-mono"
						>package.json</code
					>.
				</p>
				<p class="text-p-sm text-ink-gray-5 mt-4">
					The CSS is isolated: no Tailwind preflight reset, no global
					<code>html</code>/<code>body</code> font rules. Only the design tokens and
					component utility classes were compiled in.
				</p>
			</template>
			<template #actions>
				<Button variant="solid" @click="basicDialogOpen = false"> Got it </Button>
				<Button variant="outline" @click="basicDialogOpen = false"> Close </Button>
			</template>
		</Dialog>

		<!-- Form-style Dialog -->
		<Dialog
			v-model="formDialogOpen"
			:options="{
				title: 'Create Something',
				size: 'md',
				actions: [
					{
						label: 'Submit',
						variant: 'solid',
						onClick: handleSubmit,
					},
					{
						label: 'Cancel',
						onClick: ({ close }) => close(),
					},
				],
			}"
		>
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						v-model="formData.name"
						type="text"
						label="Name"
						placeholder="Enter a name..."
					/>
					<FormControl
						v-model="formData.description"
						type="textarea"
						label="Description"
						placeholder="Enter a description..."
					/>
				</div>
			</template>
		</Dialog>

		<!-- Confirm Dialog -->
		<Dialog
			v-model="confirmDialogOpen"
			:options="{
				title: 'Confirm Action',
				message: 'Are you sure you want to proceed? This action cannot be undone.',
				icon: { name: 'alert-triangle', theme: 'yellow' },
				actions: [
					{
						label: 'Confirm',
						variant: 'solid',
						theme: 'red',
						onClick: ({ close }) => {
							confirmResult = 'Confirmed!';
							close();
						},
					},
					{
						label: 'Cancel',
						onClick: ({ close }) => {
							confirmResult = 'Cancelled.';
							close();
						},
					},
				],
			}"
		/>

		<Combobox v-model="value" :options="repos" placeholder="Pick a repo" open-on-focus />

		<div
			v-if="lastSubmit || confirmResult"
			class="mt-6 p-3 bg-surface-gray-1 rounded-lg border border-outline-gray-1"
		>
			<p v-if="lastSubmit" class="text-p-sm text-ink-gray-7">
				Form submitted: <strong>{{ lastSubmit }}</strong>
			</p>
			<p v-if="confirmResult" class="text-p-sm text-ink-gray-7">
				Confirm dialog: <strong>{{ confirmResult }}</strong>
			</p>
		</div>
	</div>
</template>

<script setup lang="ts">
// Deep-path imports rather than the `frappe-ui` barrel.
// Why: the barrel `export *`s every component, which forces esbuild's Vue
// plugin to parse the entire library — including Calendar (uses Vue 3.4+
// `:close` shorthand) and TextEditor (uses TS-only syntax in templates)
// that the pinned `@vue/compiler-sfc@^3.2.26` cannot parse.
// Deep-path imports are also smaller: the POC bundle only carries the
// components it actually uses.
import { Button } from "frappe-ui/src/components/Button";
import { Dialog } from "frappe-ui/src/components/Dialog";
import { FormControl } from "frappe-ui/src/components/FormControl";
import { Combobox } from "frappe-ui/src/components/Combobox";
import { ref } from "vue";

const basicDialogOpen = ref(false);
const formDialogOpen = ref(false);
const confirmDialogOpen = ref(false);

const value = ref("frappe-ui");

const repos = [
	"gameplan",
	"frappe-ui",
	"frappe",
	"erpnext",
	"helpdesk",
	"crm",
	"wiki",
	"insights",
];

const formData = ref({ name: "", description: "" });
const lastSubmit = ref("");
const confirmResult = ref("");

function handleSubmit({ close }: { close: () => void }) {
	lastSubmit.value = formData.value.name
		? `"${formData.value.name}" — ${formData.value.description || "no description"}`
		: "(empty)";
	close();
}
</script>
