import path from "node:path"
import { fileURLToPath } from "node:url"
import loadTailwindConfig from "tailwindcss/loadConfig.js"
import { mergeStudioAppConfigs } from "./tailwind/studioAppConfigs.js"

const frontendDir = path.dirname(fileURLToPath(import.meta.url))
const tailwindConfig = loadTailwindConfig(path.join(frontendDir, "tailwind.config.js"))

export default {
	plugins: {
		// The editor renders every studio app, so it includes all their tailwind additions
		tailwindcss: mergeStudioAppConfigs(tailwindConfig, path.resolve(frontendDir, "../../")),
		autoprefixer: {},
	},
}
