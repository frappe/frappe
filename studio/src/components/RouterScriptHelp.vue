<template>
	<div class="text-sm leading-relaxed text-ink-gray-5">
		<p>
			The same object a standard app exports from
			<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">router.ts</code>
			, without import/export. It runs once, before the first navigation.
		</p>
		<ul class="my-2 list-disc space-y-0.5 pl-4">
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">extendRoute(route)</code>
				runs once per page with its vue-router record: set an alias, a guard or meta.
			</li>
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">setup(router)</code>
				gets the router: add redirects and global guards.
			</li>
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">options</code>
				is forwarded to createRouter, e.g. scrollBehavior.
			</li>
			<li>
				Read
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">boot</code>
				, and use
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">call</code>
				,
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">toast</code>
				and the Vue reactivity APIs directly.
			</li>
		</ul>
		<pre class="overflow-x-auto rounded-4 bg-surface-gray-2 p-2 text-xs leading-snug text-ink-gray-7">
{
  extendRoute(route) {
    if (route.name === "Tasks") route.alias = "/todo"
  },
  setup(router) {
    router.addRoute({ path: "/old-tasks", redirect: "/tasks" })
    router.beforeEach((to) => {
      if (to.meta.admin && !boot.is_admin) return { name: "Home" }
    })
  },
}</pre
		>
	</div>
</template>
