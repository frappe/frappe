# UI workspace notes

## Formatting

This repo's `.editorconfig` mandates **tabs** (indent_size 4, max_line_length 99) for
`*.vue`, `*.js`, `*.css`, `*.scss`, `*.html`. Prettier reads `.editorconfig`, so always
run it on changed files before committing to avoid the indentation/lint diff:

```bash
npx prettier --write $(git diff --name-only)
```

## FormLayout fieldtypes — also update the CRM story

When adding or changing a `FormLayout` fieldtype, mirror the change in the CRM
manual-testing story at
`apps/crm/frontend/src/pages/stories/StaticSchema.story.vue` (in addition to this
repo's `src/components/FormLayout/stories/StaticSchema.story.vue`). The CRM story
is what's used to manually test fieldtypes in a real consuming app — keep the two
stories in sync. Note CRM's frontend uses **2-space** indentation (its own
prettier/eslint config), not this repo's tabs; run `npx prettier --write` from
`apps/crm/frontend` on the CRM file.
