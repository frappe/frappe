import postcss from "postcss"
import rootToHost from "../../../ui/vite/island/root-to-host.js"

const hostLeavesTheBackground = {
	postcssPlugin: "studio-host-leaves-the-background",
	Rule(rule) {
		if (rule.selectors.every((selector) => selector === ":host")) {
			rule.walkDecls(/^background/, (declaration) => declaration.remove())
		}
	},
}

export default function hostStylesheets() {
	return {
		name: "studio-host-stylesheets",
		enforce: "post",
		generateBundle(_options, bundle) {
			const stylesheets = Object.values(bundle).filter(
				(output) => output.type === "asset" && output.fileName.endsWith(".css"),
			)
			for (const stylesheet of stylesheets) {
				this.emitFile({
					type: "asset",
					fileName: stylesheet.fileName.replace(/\.css$/, ".host.css"),
					source: postcss([rootToHost, hostLeavesTheBackground]).process(String(stylesheet.source), {
						from: undefined,
					}).css,
				})
			}
		},
	}
}
