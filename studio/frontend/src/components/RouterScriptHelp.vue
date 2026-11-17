<template>
	<div class="text-sm leading-relaxed text-ink-gray-5">
		<p>
			Control navigation between your app's pages with Vue Router. Studio creates the page routes for you.
			Write a JavaScript object with any of these optional fields:
		</p>
		<ul class="my-2 list-disc space-y-0.5 pl-4">
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">routerOptions</code>
				- passed to
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">createRouter</code>
				, e.g.
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">scrollBehavior</code>
				.
			</li>
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">extendRoute(route)</code>
				- runs once per page route, before the router is created: add an
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">alias</code>
				, set
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">meta</code>
				or check access with
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">beforeEnter</code>
				.
			</li>
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">setup(router)</code>
				- runs once after the router is created, before the first navigation. Register guards like
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">router.beforeEach</code>
				,
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">router.afterEach</code>
				.
			</li>
		</ul>
		<pre class="overflow-x-auto rounded-4 bg-surface-gray-2 p-2 text-xs leading-snug text-ink-gray-7">
{
  routerOptions: {
    scrollBehavior: () => ({ top: 0 }),
  },
  extendRoute(route) {
    if (route.name === "Tasks") route.alias = "/todo"
  },
  setup(router) {
    router.beforeEach((to) => {
      if (
       boot.onboarding_complete === false
       && to.name !== 'Onboarding'
      ) {
        return { name: 'Onboarding' }
      }
    })
  },
}</pre
		>
	</div>
</template>
