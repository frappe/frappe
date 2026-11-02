import { fileURLToPath } from "node:url"

export default {
	plugins: {
		tailwindcss: { config: fileURLToPath(new URL("./tailwind.editor.config.js", import.meta.url)) },
		autoprefixer: {},
	},
}
