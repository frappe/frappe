# DataImport

The Data Import screen from Desk, as Vue components. An import goes through four
steps: Config, Map columns, Fix issues and Import.

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
- `@open-imports` comes from Config's "Review pending imports": show the app's
  list of Data Import records, filtered to that document type and `Pending`.
- `@new-import` is optional. When set, a finished import offers "Start new
  import" (and Retry steps back unless the run timed out); open a new import of
  that document type.
- The wizard fills its parent's height, so it works in a page or a `Dialog`.

## Moving from DataImport

The `DataImport` page is gone. It read the route itself and took a `doctypeMap`
for its links; now the app owns the name and the links.

Its list of past imports is gone too. Show Data Import records with the app's
own list view, and open the wizard from a row or a create button.

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
