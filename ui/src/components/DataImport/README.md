# DataImport

The Data Import screen from Desk, as Vue components. An import goes through four
steps: Config, Preview, Fix issues and Import.

`useDataImport` loads and saves the import, fetches the preview, starts and stops
the run and listens for its progress. `<DataImportWizard>` only shows it. Use the
two together.

## Usage

```vue
<script setup lang="ts">
import { ref } from "vue";
import { DataImportWizard, useDataImport } from "@framework/ui";

// null starts a new import; the name is filled in once it is first saved
const name = ref<string | null>(route.params.importName ?? null);
const dataImport = useDataImport(name, { doctype: "CRM Lead" });
</script>

<template>
  <DataImportWizard
    :dataImport="dataImport"
    @open-list="(doctype) => router.push({ name: 'Leads' })"
    @open-record="(doctype, docname) => router.push(`/leads/${docname}`)"
    @open-imports="(doctype) => router.push(`/data-import?doctype=${doctype}`)"
    @new-import="(doctype) => router.push(`/data-import/doctype/${doctype}`)"
  />
</template>
```

- `doctype` picks the document type for a new import. Leave it out to let the
  user choose it on Config. Pass a getter (`() => route.params.doctype`) if the
  page stays mounted while `name` goes back to `null` for another new import.
- Change `name` to open another import. Watch it to keep your URL in step after
  the first save.
- There is no router inside. `@open-list` and `@open-record` ask the app to open
  the list or a record; ignore them if the app has no such page.
- `@open-imports` comes from Config's "Review pending imports": show the
  pending imports of that document type, for example a `DataImportList` built
  with `useDataImportList({ doctype, status: "Pending" })`.
- `@new-import` is optional. When set, a failed import offers "Start new
  import" (and Retry steps back unless the run timed out); open a new import of
  that document type.
- The wizard fills its parent's height, so it works in a page or a `Dialog`.

## List of imports

`useDataImportList` fetches past imports, newest first, with search, a status
filter and Load More. `<DataImportList>` shows them. It has no title of its own;
the app's page header shows one.

```vue
<script setup lang="ts">
import { DataImportList, useDataImportList } from "@framework/ui";

const list = useDataImportList({ doctype: "CRM Lead" });
</script>

<template>
  <DataImportList
    :list="list"
    @open="(name) => router.push(`/data-import/${name}`)"
    @new="() => router.push('/data-import/new')"
  />
</template>
```

- `doctype` shows only imports of that document type. Leave it out to show all.
- `@open` gives the import's name; pass it to `useDataImport` to open it.
- `@new` is the Import button. Open the wizard with `name` set to `null`; nothing
  is saved until the user picks a file.
- `list.reload()` fetches again, for example after the wizard closes in a
  `Dialog`.

## Moving from DataImport

The `DataImport` page is gone. It read the route itself and took a `doctypeMap`
for its links; now the app owns the name and the links.

Before:

```vue
<DataImport
  :doctype="doctype"
  :importName="route.params.importName"
  :doctypeMap="{ 'LMS Course': { title: 'Courses', listRoute: '/courses' } }"
/>
```

After:

```vue
<script setup lang="ts">
const name = ref(route.params.importName ?? null);
watch(name, (next) => router.replace({ params: { importName: next } }));
const dataImport = useDataImport(name, { doctype });
</script>

<template>
  <DataImportWizard
    :dataImport="dataImport"
    @open-list="() => router.push('/courses')"
    @open-record="(doctype, docname) => router.push(`/courses/${docname}`)"
  />
</template>
```

`label`, `description` and `socket` are no longer needed: put any heading above
the wizard yourself, and the wizard uses the app's socket on its own.

The old public types `DataImportRecord`, `DataImportProps`, `DataImportSocket`
and `DataImports` were removed.
