import fs from "fs"
import path from "path"
import { createRequire } from "module"

// frappe-ui's Tailwind icon plugin resolves lucide-static from frappe-ui's own folder; resolve it
// from there too so the icon picker never lists icons the editor has no CSS for
export default function lucideStaticAlias(frontendDir) {
	const frappeUIPackage = fs.realpathSync(path.resolve(frontendDir, "node_modules/frappe-ui/package.json"))
	const lucideStaticPackage = createRequire(frappeUIPackage).resolve("lucide-static/package.json")
	return { find: /^lucide-static(?=\/|$)/, replacement: path.dirname(lucideStaticPackage) }
}
