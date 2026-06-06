# UI workspace notes

## Formatting

This repo's `.editorconfig` mandates **tabs** (indent_size 4, max_line_length 99) for
`*.vue`, `*.js`, `*.css`, `*.scss`, `*.html`. Prettier reads `.editorconfig`, so always
run it on changed files before committing to avoid the indentation/lint diff:

```bash
npx prettier --write $(git diff --name-only)
```
