// Restore the PUBLISHED frappe-ui. If node_modules/frappe-ui is a symlink to a
// local checkout (created by `yarn dev:frappe-ui`), remove it and reinstall the
// package from the lockfile. This runs before plain `yarn dev` and `yarn build`,
// so switching back from local-frappe-ui work is automatic. No-op (and cheap)
// when nothing is linked.
import { lstatSync, unlinkSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { execSync } from "node:child_process"

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const linkPath = resolve(frontendDir, "node_modules/frappe-ui")
const stat = lstatSync(linkPath, { throwIfNoEntry: false })

if (stat?.isSymbolicLink()) {
	console.log("↩  Unlinking local frappe-ui; restoring the published package…")
	// unlinkSync removes the symlink itself; never follows it into the checkout.
	unlinkSync(linkPath)
	// Reinstall just what's missing from the lockfile (the published frappe-ui).
	execSync("yarn install --check-files", { cwd: frontendDir, stdio: "inherit" })
}
