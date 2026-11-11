import { build } from "vite"
await build({ root: process.cwd(), logLevel: "error", build: { outDir: process.argv[2], emptyOutDir: true, minify: false } })
