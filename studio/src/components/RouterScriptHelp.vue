<template>
	<div class="text-sm leading-relaxed text-ink-gray-5">
		<p>
			Control navigation between your app's pages with Vue Router. Studio creates the page routes for you.
			Write a JavaScript object with any of these optional fields:
		</p>
		<ul class="my-2 list-disc space-y-0.5 pl-4">
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">extendRoute(route)</code>
				- customise each page's route before the router is created. Add an
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">alias</code>
				for another URL, set
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">meta</code>
				or check access with
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">beforeEnter</code>
				.
			</li>
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">options</code>
				- configure the router, for example how the page scrolls after navigation with
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">scrollBehavior</code>
				.
			</li>
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">setup(router)</code>
				— runs once after the router is created, before the first navigation. Register navigation guards like
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">beforeEach</code>
				,
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">afterEach</code>
				to allow, cancel or redirect navigation.
			</li>
		</ul>
		<pre class="overflow-x-auto rounded-4 bg-surface-gray-2 p-2 text-xs leading-snug text-ink-gray-7">
{
  options: {
    scrollBehavior: () => ({ top: 0 }),
  },
  extendRoute(route) {
    if (route.name === "Tasks") route.alias = "/todo"
  },
  setup(router) {
    router.beforeEach((to) => {
      if (to.path === "/old-tasks") return { name: "Tasks" }
    })
  },
}</pre
		>
	</div>
</template>
