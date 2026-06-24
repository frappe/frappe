import type { BlockOptions, BlockStyleMap } from "@/types";

function getBlockTemplate(
	type:
		| "body"
		| "container"
		| "fit-container"
		| "header"
		| "fallback-component"
		| "empty-component"
		| "missing-component"
): BlockOptions {
	switch (type) {
		case "body":
			return {
				componentId: "root",
				componentName: "div",
				blockName: "body",
				originalElement: "body",
				children: [],
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					flexShrink: 0,
					width: "inherit",
					overflowX: "hidden",
					height: "100%",
				}
			};

		case "container":
			return {
				componentName: "container",
				originalElement: "div",
				blockName: "container",
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					flexShrink: 1,
				} as BlockStyleMap,
			};

		case "fit-container":
			return {
				componentName: "container",
				originalElement: "div",
				blockName: "container",
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					flexShrink: 1,
					height: "fit-content",
					width: "fit-content",
				} as BlockStyleMap,
			};

		case "header":
			return {
				componentName: "header",
				blockName: "header",
				originalElement: "header",
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					width: "100%",
					height: "fit-content",
					padding: "10px 12px",
					backgroundColor: "var(--surface-base)",
					borderStyle: "solid",
					borderWidth: "0px 0px 1px 0px",
					borderColor: "var(--outline-gray-1)",
				} as BlockStyleMap,
				children: [
					{
						componentName: "Breadcrumbs",
						componentProps: {
							items: [
								{
									label: "Home",
									route: { name: "Home" },
								},
								{
									label: "List",
									route: "/components/breadcrumbs",
								},
							],
						}
					},
					{
						componentName: "Button",
						componentProps: {
							label: "Create",
							iconLeft: "plus",
							variant: "solid",
						},
						baseStyles: {
							marginLeft: "auto",
						} as BlockStyleMap,
					}
				],
			}

		case "fallback-component":
			return {
				componentName: "p",
				originalElement: "__raw_html__",
				innerHTML: `<div style="color: red;background: #f4f4f4;display:flex;flex-direction:column;position:static;top:auto;left:auto;width: 600px;height: 275px;align-items:center;font-size: 30px;justify-content:center"><p>Component missing</p></div>`,
				baseStyles: {
					height: "fit-content",
					width: "fit-content",
				}
			}

		case "empty-component":
			return {
				componentName: "container",
				originalElement: "div",
				baseStyles: {
					height: "200px",
					width: "100%",
				} as BlockStyleMap,
			};

		case "missing-component":
			return {
				componentName: "HTML",
				originalElement: "__raw_html__",
				innerHTML: `<div style="color:#E86C13;background:#F8F8F8;display:flex;width:300px;height:150px;align-items:center;font-size:16px;justify-content:center"><p>Component Missing</p></div>`,
				baseStyles: {
					height: "fit-content",
					width: "fit-content",
				} as BlockStyleMap,
			};
	}
}

export default getBlockTemplate;