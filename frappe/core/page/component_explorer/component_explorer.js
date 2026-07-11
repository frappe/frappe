frappe.pages["component-explorer"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Component Explorer"),
		single_column: true,
	});

	// Examples are grouped (all variants together, all sizes together...).
	// Each item's opts object is both the displayed code and the real input
	// for the live preview — what you see is exactly what runs.
	const COMPONENTS = {
		Dropdown: {
			helper: "frappe.ui.dropdown",
			groups: [
				{
					title: __("Basic actions"),
					items: [
						{
							button: { label: "Options" },
							options: [
								{
									label: "Edit",
									icon: "pen",
									onclick: () => frappe.ui.toast({ message: "Edit clicked" }),
								},
								{
									label: "Duplicate",
									icon: "copy",
									onclick: () => frappe.ui.toast({ message: "Duplicated" }),
								},
								{
									label: "Delete",
									icon: "trash-2",
									theme: "red",
									onclick: () =>
										frappe.ui.toast({ message: "Deleted", type: "error" }),
								},
							],
						},
					],
				},
				{
					title: __("Groups, shortcuts and disabled rows"),
					items: [
						{
							button: { label: "File" },
							options: [
								{
									group: "Document",
									options: [
										{
											label: "Rename",
											shortcut: "ctrl+r",
											onclick: () =>
												frappe.ui.toast({ message: "Rename clicked" }),
										},
										{
											label: "Print",
											shortcut: "ctrl+p",
											onclick: () =>
												frappe.ui.toast({ message: "Print clicked" }),
										},
									],
								},
								{
									group: "Danger zone",
									options: [
										{ label: "Archive", disabled: true },
										{
											label: "Delete permanently",
											theme: "red",
											onclick: () =>
												frappe.ui.toast({
													message: "Deleted",
													type: "error",
												}),
										},
									],
								},
							],
						},
					],
				},
				{
					title: __("Submenus"),
					items: [
						{
							button: { label: "Actions" },
							options: [
								{
									label: "Open",
									icon: "external-link",
									onclick: () => frappe.ui.toast({ message: "Opened" }),
								},
								{
									label: "Move to",
									icon: "folder",
									submenu: [
										{
											label: "Inbox",
											onclick: () =>
												frappe.ui.toast({ message: "Moved to Inbox" }),
										},
										{
											label: "Archive",
											onclick: () =>
												frappe.ui.toast({ message: "Moved to Archive" }),
										},
										{
											label: "More...",
											submenu: [
												{
													label: "Folder A",
													onclick: () =>
														frappe.ui.toast({
															message: "Moved to Folder A",
														}),
												},
												{
													label: "Folder B",
													onclick: () =>
														frappe.ui.toast({
															message: "Moved to Folder B",
														}),
												},
											],
										},
									],
								},
							],
						},
					],
				},
				{
					title: __("Selected row, descriptions and links"),
					items: [
						{
							button: { label: "View" },
							options: [
								{
									label: "List",
									selected: true,
									onclick: () => frappe.ui.toast({ message: "List view" }),
								},
								{
									label: "Kanban",
									description: "Drag cards between columns",
									onclick: () => frappe.ui.toast({ message: "Kanban view" }),
								},
								{
									label: "Documentation",
									icon: "book-open",
									href: "https://docs.frappe.io",
								},
							],
						},
					],
				},
				{
					title: __("Placement and empty state"),
					items: [
						{
							button: { label: "Opens top-end" },
							side: "top",
							align: "end",
							options: [
								{
									label: "One",
									onclick: () => frappe.ui.toast({ message: "One" }),
								},
								{
									label: "Two",
									onclick: () => frappe.ui.toast({ message: "Two" }),
								},
							],
						},
						{
							button: { label: "No items" },
							options: [],
							empty_text: "Nothing here yet",
						},
					],
				},
			],
		},
		"Context Menu": {
			helper: "new frappe.ui.ContextMenu",
			code_lead: "target: row_el",
			stacked: true,
			make: (opts) => {
				const $surface = $(
					`<div class="rounded-md border px-4 py-4 text-base text-ink-gray-6" style="border-style: dashed">${frappe.utils.escape_html(
						opts.__surface || __("Right-click here")
					)}</div>`
				);
				new frappe.ui.ContextMenu({ target: $surface, ...opts });
				return $surface;
			},
			groups: [
				{
					title: __("Basic"),
					items: [
						{
							options: [
								{
									label: "Cut",
									shortcut: "ctrl+x",
									onclick: () => frappe.ui.toast({ message: "Cut" }),
								},
								{
									label: "Copy",
									shortcut: "ctrl+c",
									onclick: () => frappe.ui.toast({ message: "Copied" }),
								},
								{
									label: "Paste",
									shortcut: "ctrl+v",
									onclick: () => frappe.ui.toast({ message: "Pasted" }),
								},
								{
									label: "Delete",
									theme: "red",
									onclick: () =>
										frappe.ui.toast({ message: "Deleted", type: "error" }),
								},
							],
						},
					],
				},
				{
					title: __("Groups and submenus"),
					items: [
						{
							__surface: __("Right-click this task card"),
							options: [
								{
									group: "Task",
									options: [
										{
											label: "Open",
											icon: "external-link",
											onclick: () => frappe.ui.toast({ message: "Opened" }),
										},
										{
											label: "Assign to",
											icon: "user-plus",
											submenu: [
												{
													label: "John Doe",
													onclick: () =>
														frappe.ui.toast({
															message: "Assigned to John",
														}),
												},
												{
													label: "Jane Smith",
													onclick: () =>
														frappe.ui.toast({
															message: "Assigned to Jane",
														}),
												},
											],
										},
									],
								},
								{
									group: "Board",
									options: [
										{
											label: "Move to Done",
											icon: "circle-check",
											onclick: () =>
												frappe.ui.toast({
													message: "Moved to Done",
													type: "success",
												}),
										},
									],
								},
							],
						},
					],
				},
			],
		},
		Tooltip: {
			helper: "frappe.ui.tooltip",
			code_first: "button_el",
			make: (opts) => {
				const $btn = frappe.ui.button({ label: opts.__trigger || __("Hover me") });
				frappe.ui.tooltip($btn, opts);
				return $btn;
			},
			groups: [
				{
					title: __("Basic (hover, or focus with Tab)"),
					items: [
						{
							__trigger: __("Hover me"),
							text: "Adds a row below",
						},
					],
				},
				{
					title: __("Sides"),
					items: [
						{
							__trigger: __("Top"),
							text: "Top is the default",
						},
						{
							__trigger: __("Right"),
							text: "Opens right",
							side: "right",
						},
						{
							__trigger: __("Bottom"),
							text: "Opens bottom",
							side: "bottom",
						},
						{
							__trigger: __("Left"),
							text: "Opens left",
							side: "left",
						},
					],
				},
				{
					title: __("Delay"),
					items: [
						{
							__trigger: __("No delay"),
							text: "Shows immediately",
							delay: 0,
						},
						{
							__trigger: __("Slow"),
							text: "Shows after a second",
							delay: 1000,
						},
					],
				},
				{
					title: __("Long text (wraps)"),
					items: [
						{
							__trigger: __("Long"),
							text: "A longer explanation that wraps across a couple of lines instead of running off the screen",
						},
					],
				},
			],
		},
		Toast: {
			helper: "frappe.ui.toast",
			html: (opts) => "",
			groups: [
				{
					title: __("Types"),
					items: [
						{
							__label: __("Message (default, no icon)"),
							__code: 'frappe.ui.toast({ message: "Draft restored" })',
							__run: () => frappe.ui.toast({ message: "Draft restored" }),
						},
						{
							__label: __("Info"),
							__code: 'frappe.ui.toast({ message: "3 documents queued", type: "info" })',
							__run: () =>
								frappe.ui.toast({ message: "3 documents queued", type: "info" }),
						},
						{
							__label: __("Success"),
							__code: 'frappe.ui.toast({ message: "Saved", type: "success" })',
							__run: () => frappe.ui.toast({ message: "Saved", type: "success" }),
						},
						{
							__label: __("Warning"),
							__code: 'frappe.ui.toast({ message: "Low stock for Item A", type: "warning" })',
							__run: () =>
								frappe.ui.toast({
									message: "Low stock for Item A",
									type: "warning",
								}),
						},
						{
							__label: __("Error"),
							__code: 'frappe.ui.toast({ message: "Could not connect", type: "error" })',
							__run: () =>
								frappe.ui.toast({ message: "Could not connect", type: "error" }),
						},
					],
				},
				{
					title: __("With description"),
					items: [
						{
							__label: __("Show with description"),
							__code: 'frappe.ui.toast({ message: "Import finished", description: "42 rows created, 3 skipped", type: "success" })',
							__run: () =>
								frappe.ui.toast({
									message: "Import finished",
									description: "42 rows created, 3 skipped",
									type: "success",
								}),
						},
					],
				},
				{
					title: __("With action"),
					items: [
						{
							__label: __("Show with Undo"),
							__code: 'frappe.ui.toast({ message: "Email sent", type: "success", action: { label: "Undo", onclick: () => frappe.ui.toast({ message: "Undone" }) } })',
							__run: () =>
								frappe.ui.toast({
									message: "Email sent",
									type: "success",
									action: {
										label: "Undo",
										onclick: () => frappe.ui.toast({ message: "Undone" }),
									},
								}),
						},
					],
				},
				{
					title: __("Same id updates in place"),
					items: [
						{
							__label: __("Run 3-step progress"),
							__code: 'frappe.ui.toast({ id: "sync", message: "Step " + n + " of 3...", type: "info" })',
							__run: () => {
								let n = 0;
								const step = () => {
									n += 1;
									frappe.ui.toast({
										id: "sync",
										message: n < 3 ? `Step ${n} of 3...` : "All steps done",
										type: n < 3 ? "info" : "success",
									});
									if (n < 3) setTimeout(step, 900);
								};
								step();
							},
						},
					],
				},
				{
					title: __("Custom icon"),
					items: [
						{
							__label: __("Show custom icon"),
							__code: 'frappe.ui.toast({ message: "New feature unlocked", icon: "sparkles", icon_class: "text-ink-violet-5" })',
							__run: () =>
								frappe.ui.toast({
									message: "New feature unlocked",
									icon: "sparkles",
									icon_class: "text-ink-violet-5",
								}),
						},
					],
				},
				{
					title: __("Legacy html content (frappe.show_alert)"),
					items: [
						{
							__label: __("HTML message with inline link"),
							__code: 'frappe.show_alert({ message: `Email sent <span data-action="undo" style="text-decoration: underline; cursor: pointer">Undo</span>`, indicator: "green" }, 7, { undo: () => frappe.ui.toast({ message: "Undone" }) })',
							__run: () =>
								frappe.show_alert(
									{
										message:
											'Email sent <span data-action="undo" style="text-decoration: underline; cursor: pointer">Undo</span>',
										indicator: "green",
									},
									7,
									{ undo: () => frappe.ui.toast({ message: "Undone" }) }
								),
						},
						{
							__label: __("Unsafe html gets stripped"),
							__code: 'frappe.show_alert({ message: `<b>Bold is fine</b> <img src=x onerror="alert(1)"> <a href="javascript:alert(1)">bad link</a>`, indicator: "blue" })',
							__run: () =>
								frappe.show_alert({
									message:
										'<b>Bold is fine</b> <img src=x onerror="alert(1)"> <a href="javascript:alert(1)">bad link</a>',
									indicator: "blue",
								}),
						},
					],
				},
				{
					title: __("Follows a promise"),
					items: [
						{
							__label: __("Promise that succeeds"),
							__code: 'frappe.ui.toast.promise(save(), { loading: "Saving...", success: "Saved", error: "Failed to save" })',
							__run: () =>
								frappe.ui.toast.promise(
									new Promise((resolve) => setTimeout(resolve, 1500)),
									{
										loading: "Saving...",
										success: "Saved",
										error: "Failed to save",
									}
								),
						},
						{
							__label: __("Promise that fails"),
							__code: 'frappe.ui.toast.promise(save(), { loading: "Saving...", success: "Saved", error: (e) => e.message })',
							__run: () =>
								frappe.ui.toast
									.promise(
										new Promise((_, reject) =>
											setTimeout(
												() => reject(new Error("Server timed out")),
												1500
											)
										),
										{
											loading: "Saving...",
											success: "Saved",
											error: (e) => e.message,
										}
									)
									.catch(() => {}),
						},
					],
				},
			],
		},
		Alert: {
			helper: "frappe.ui.alert",
			html: (opts) => frappe.ui.alert.html(opts),
			stacked: true,
			groups: [
				{
					title: __("Themes"),
					items: [
						{ title: "Heads up — plain gray, no icon" },
						{ title: "Your draft was restored", theme: "blue" },
						{ title: "This document is locked", theme: "yellow" },
						{ title: "Import failed for 3 rows", theme: "red" },
						{ title: "All checks passed", theme: "green" },
					],
				},
				{
					title: __("With description"),
					items: [
						{
							title: "Scheduled maintenance",
							description:
								"The site will be read-only on Sunday between 02:00 and 04:00 UTC.",
							theme: "blue",
						},
					],
				},
				{
					title: __("Variants"),
					items: [
						{ title: "Subtle is the default", theme: "blue", variant: "subtle" },
						{
							title: "Outline keeps the icon, drops the fill",
							theme: "blue",
							variant: "outline",
						},
						{ title: "Plain outline", variant: "outline" },
					],
				},
				{
					title: __("Dismissible"),
					items: [
						{
							title: "Saved successfully",
							theme: "green",
							dismissible: true,
							on_dismiss: () => frappe.show_alert(__("Alert dismissed")),
						},
					],
				},
				{
					title: __("Custom icon + footer"),
					items: [
						{
							title: "New experimental feature",
							description: "Turn it on from the settings panel.",
							icon: "flask-conical",
							footer: () =>
								frappe.ui.button({
									label: "Open Settings",
									size: "sm",
									variant: "outline",
									onclick: () => frappe.show_alert(__("Opening settings...")),
								}),
						},
					],
				},
			],
		},
		Button: {
			helper: "frappe.ui.button",
			html: (opts) => frappe.ui.button.html(opts),
			groups: [
				{
					title: __("Variants"),
					items: [
						{ label: "Save" },
						{ label: "Submit", variant: "solid" },
						{ label: "Cancel", variant: "outline" },
						{ label: "More", variant: "ghost" },
						{ label: "Delete", variant: "solid", theme: "red" },
					],
				},
				{
					title: __("Icons"),
					items: [
						{ label: "Add", icon: "plus" },
						{ label: "Next", icon_right: "chevron-right" },
						{ icon: "settings", title: "Settings", variant: "ghost" },
						{ icon: "bell", tooltip: "Notifications", variant: "ghost" },
					],
				},
				{
					title: __("Sizes"),
					items: [
						{ label: "Extra small", size: "xs" },
						{ label: "Small" },
						{ label: "Medium", size: "md" },
						{ label: "Large", size: "lg" },
					],
				},
				{
					title: __("States"),
					items: [
						{ label: "Save", loading: true },
						{ label: "Save", disabled: true },
					],
				},
			],
		},
		Avatar: {
			helper: "frappe.ui.avatar",
			html: (opts) => frappe.ui.avatar.html(opts),
			groups: [
				{
					title: __("With image"),
					items: [
						{
							label: "John Doe",
							image: "https://avatars.githubusercontent.com/u/499550?s=60&v=4",
						},
						{
							label: "Jane Smith",
							image: "https://avatars.githubusercontent.com/u/1?s=60&v=4",
							size: "2xl",
						},
						{
							label: "Sam Smith",
							image: "https://avatars.githubusercontent.com/u/2?s=60&v=4",
							shape: "square",
							size: "2xl",
						},
					],
				},
				{
					title: __("Fallback themes"),
					items: [
						{ label: "John Doe" },
						{ label: "Jane Smith", theme: "blue" },
						{ label: "Sam Smith", theme: "green" },
						{ label: "Alice Adams", theme: "amber" },
						{ label: "Ryan Reed", theme: "red" },
						{ label: "Violet Vane", theme: "violet" },
					],
				},
				{
					title: __("Sizes"),
					items: [
						{ label: "John Doe", size: "xs" },
						{ label: "John Doe", size: "sm" },
						{ label: "John Doe" },
						{ label: "John Doe", size: "lg" },
						{ label: "John Doe", size: "xl" },
						{ label: "John Doe", size: "2xl" },
						{ label: "John Doe", size: "3xl" },
					],
				},
				{
					title: __("Shapes"),
					items: [
						{ label: "John Doe", theme: "blue" },
						{ label: "John Doe", theme: "blue", shape: "square" },
						{ label: "John Doe", theme: "blue", shape: "square", size: "2xl" },
					],
				},
				{
					title: __("With indicator"),
					items: [
						{
							label: "John Doe",
							image: "https://avatars.githubusercontent.com/u/499550?s=60&v=4",
							indicator: "green",
							size: "xl",
						},
						{ label: "Jane Smith", theme: "blue", indicator: "gray", size: "xl" },
						{ label: "Sam Smith", theme: "violet", indicator: "red", size: "2xl" },
					],
				},
			],
		},
		Skeleton: {
			helper: "frappe.ui.skeleton",
			html: (opts) => frappe.ui.skeleton.html(opts),
			groups: [
				{
					title: __("Sizes"),
					items: [
						{ width: "120px", height: "16px" },
						{ width: "240px", height: "16px" },
						{ width: "100%", height: "40px" },
					],
				},
				{
					title: __("Shapes"),
					items: [
						{ width: "32px", height: "32px", css_class: "rounded-full" },
						{ width: "180px", height: "12px", css_class: "rounded-full" },
					],
				},
			],
		},
		Divider: {
			helper: "frappe.ui.divider",
			html: (opts) => frappe.ui.divider.html(opts),
			groups: [
				{
					title: __("Plain"),
					items: [{}],
				},
				{
					title: __("With action"),
					items: [
						{ action: { label: "Load More" } },
						{ action: { label: "Show all" }, position: "start" },
					],
				},
				{
					title: __("Vertical (in a flex row)"),
					items: [{ orientation: "vertical", flex_item: true }],
				},
			],
		},
		Breadcrumbs: {
			helper: "frappe.ui.breadcrumbs",
			html: (opts) => frappe.ui.breadcrumbs.html(opts),
			stacked: true,
			groups: [
				{
					title: __("Links"),
					items: [
						{
							items: [
								{ label: "Home", href: "/app" },
								{ label: "Accounting", href: "#" },
								{ label: "Sales Invoice" },
							],
						},
					],
				},
				{
					title: __("With click handlers"),
					items: [
						{
							items: [
								{
									label: "Projects",
									onclick: () => frappe.show_alert(__("Going to Projects")),
								},
								{ label: "Website Redesign" },
							],
						},
					],
				},
				{
					title: __("Prefix, suffix and icon-only crumbs"),
					items: [
						{
							items: [
								{ prefix: "house", title: "Home", href: "#" },
								{ label: "Inbox", prefix: "mail", href: "#" },
								{ label: "Quarterly Report", suffix: "lock" },
							],
						},
					],
				},
				{
					title: __("Long current page (truncates)"),
					items: [
						{
							items: [
								{ label: "Home", href: "#" },
								{
									label: "A very long document title that will not fit and gets cut off with an ellipsis at some point",
								},
							],
						},
					],
				},
			],
		},
		Badge: {
			helper: "frappe.ui.badge",
			html: (opts) => frappe.ui.badge.html(opts),
			groups: [
				{
					title: __("Themes"),
					items: [
						{ label: "Open" },
						{ label: "Info", theme: "blue" },
						{ label: "Success", theme: "green" },
						{ label: "Warning", theme: "amber" },
						{ label: "Overdue", theme: "red" },
						{ label: "Special", theme: "violet" },
					],
				},
				{
					title: __("Variants"),
					items: [
						{ label: "Subtle" },
						{ label: "Solid", theme: "red", variant: "solid" },
						{ label: "Outline", variant: "outline" },
						{ label: "Ghost", variant: "ghost" },
					],
				},
				{
					title: __("Sizes"),
					items: [
						{ label: "Small", theme: "blue", size: "sm" },
						{ label: "Medium", theme: "blue" },
						{ label: "Large", theme: "blue", size: "lg" },
					],
				},
				{
					title: __("With icon"),
					items: [
						{ label: "Small", theme: "green", icon: "check", size: "sm" },
						{ label: "Medium", theme: "blue", icon: "check" },
						{ label: "Large", theme: "red", icon: "check", size: "lg" },
					],
				},
			],
		},
	};

	// ---- code column: turn an opts object into copy-paste-ready code ----
	// Short values stay on one line; anything longer breaks into indented
	// lines, the way a person would write it. Keys starting with "__" are
	// explorer plumbing (labels, trigger text, canned code), not part of
	// the call, so they never print.
	const MAX_INLINE = 68;
	const INDENT = "  ";

	// join the parts on one line if the result is short enough, otherwise
	// put one part per line, indented one level deeper than the parent
	function wrap(parts, open, close, depth, spaced) {
		if (!parts.length) return `${open}${close}`;
		const one_line = spaced
			? `${open} ${parts.join(", ")} ${close}`
			: `${open}${parts.join(", ")}${close}`;
		if (one_line.length <= MAX_INLINE && !one_line.includes("\n")) return one_line;
		const pad = INDENT.repeat(depth + 1);
		return `${open}\n${pad}${parts.join(`,\n${pad}`)}\n${INDENT.repeat(depth)}${close}`;
	}

	function format_value(value, depth) {
		if (typeof value === "function") {
			// print the real handler, collapsing the source file's own
			// wrapping/indentation so it reads as one clean expression
			return value.toString().replace(/\n\s*/g, " ");
		}
		if (Array.isArray(value)) {
			return wrap(
				value.map((entry) => format_value(entry, depth + 1)),
				"[",
				"]",
				depth
			);
		}
		if (value && typeof value === "object") {
			const entries = Object.entries(value).filter(([key]) => !key.startsWith("__"));
			return wrap(
				entries.map(([key, entry]) => `${key}: ${format_value(entry, depth + 1)}`),
				"{",
				"}",
				depth,
				true
			);
		}
		return JSON.stringify(value);
	}

	function to_code(component, opts) {
		const entries = Object.entries(opts).filter(([key]) => !key.startsWith("__"));
		const parts = entries.map(([key, entry]) => `${key}: ${format_value(entry, 1)}`);
		// e.g. ContextMenu takes a target element we can't print for real
		if (component.code_lead) parts.unshift(component.code_lead);
		const object_code = wrap(parts, "{", "}", 0, true);
		// e.g. tooltip's first argument is the trigger element
		const first = component.code_first ? `${component.code_first}, ` : "";
		return `${component.helper}(${first}${object_code})`;
	}

	// "frappe.ui.alert" -> the callable helper (element form, so handlers work)
	function helper_fn(path) {
		return path.split(".").reduce((obj, key) => obj[key], window);
	}

	const $body = $(`
		<div class="explorer flex flex-col gap-4 px-4 py-4">
			<div class="explorer-picker"></div>
			<div class="explorer-groups flex flex-col gap-4"></div>
		</div>
	`).appendTo(page.main);

	function render_component(name) {
		const component = COMPONENTS[name];
		const $groups = $body.find(".explorer-groups").empty();
		if (!component) return;

		component.groups.forEach((group) => {
			const $group = $(`
				<div class="explorer-group flex flex-col gap-2">
					<div class="text-base-semibold text-ink-gray-8">${frappe.utils.escape_html(group.title)}</div>
					<div class="flex gap-3 items-stretch">
						<pre class="flex-1 rounded-md border m-0 px-4 py-3 text-ink-gray-8 text-p-sm overflow-x-auto"><code></code></pre>
						<div class="flex-1 min-w-0 flex ${
							component.stacked ? "flex-col items-stretch" : "flex-wrap items-center"
						} gap-2 rounded-md border px-4 py-4 explorer-preview"></div>
					</div>
				</div>
			`);
			const code = group.items
				.map((opts) => opts.__code || to_code(component, opts))
				.join("\n");
			$group.find("code").text(code);
			const $preview = $group.find(".explorer-preview");
			const make = component.make || helper_fn(component.helper);
			group.items.forEach((opts) => {
				// some things (like toasts) show themselves elsewhere — those
				// items carry their own code text and a Run trigger
				if (opts.__run) {
					$preview.append(
						frappe.ui.button({
							label: opts.__label || __("Run"),
							size: "sm",
							variant: "outline",
							onclick: opts.__run,
						})
					);
					return;
				}
				$preview.append(make(opts));
			});
			$groups.append($group);
		});
	}

	const picker = frappe.ui.form.make_control({
		parent: $body.find(".explorer-picker"),
		df: {
			fieldtype: "Autocomplete",
			fieldname: "component",
			label: __("Component"),
			options: Object.keys(COMPONENTS).sort(),
			change: () => render_component(picker.get_value()),
		},
		render_input: true,
	});

	picker.set_value("Button");
	render_component("Button");
};
