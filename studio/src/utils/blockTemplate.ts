import type { BlockOptions, BlockStyleMap } from "@/types";

function getBlockTemplate(
	type:
		| "body"
		| "container"
		| "fallback-component"
): BlockOptions {
	switch (type) {
		case "body":
			return {
				componentId: "root",
				componentName: "div",
				originalElement: "body",
				children: [],
				baseStyles: {
					display: "flex",
					flexWrap: "wrap",
					flexDirection: "column",
					flexShrink: 0,
					alignItems: "center",
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
					flexDirection: "column",
					flexShrink: 0,
					overflow: "hidden",
				} as BlockStyleMap,
			};

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
	}
}

export default getBlockTemplate;