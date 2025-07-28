# SQLite Search Framework

SQLite Search is a full-text search framework for Frappe applications that provides advanced search capabilities using SQLite's FTS5 (Full-Text Search) engine. It offers features like spelling correction, time-based recency scoring, custom ranking, permission-aware filtering, and extensible scoring pipelines.

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Features & Customization](#features--customization)
- [API Reference](#api-reference)

## Quick Start

### 1. Create a Search Class

Create a search implementation by extending `SQLiteSearch`:

```python
# my_app/search.py
from frappe.search.sqlite_search import SQLiteSearch

class MyAppSearch(SQLiteSearch):
    # Database file name
    INDEX_NAME = "my_app_search.db"

    # Define the search schema
    INDEX_SCHEMA = {
        "metadata_fields": ["project", "owner", "status"],
        "tokenizer": "unicode61 remove_diacritics 2 tokenchars '-_'",
    }

    # Define which doctypes to index and their field mappings
    INDEXABLE_DOCTYPES = {
        "Task": {
            "fields": ["name", {"title": "subject"}, {"content": "description"}, "modified", "project", "owner", "status"],
        },
        "Issue": {
            "fields": ["name", "title", "description", {"modified": "last_updated"}, "project", "owner"],
            "filters": {"status": ("!=", "Closed")},  # Only index non-closed issues
        },
    }

    def get_search_filters(self):
        """Return permission filters for current user"""
        # Get projects accessible to current user
        accessible_projects = frappe.get_all(
            "Project",
            filters={"owner": frappe.session.user},
            pluck="name"
        )

        if not accessible_projects:
            return {"project": []}  # No access

        return {"project": accessible_projects}
```

### 2. Register the Search Class

Add your search class to hooks.py:

```python
# my_app/hooks.py
sqlite_search = ['my_app.search.MyAppSearch']
```

### 3. Create API Endpoint

Create a whitelisted method to expose search functionality:

```python
# my_app/api.py
import frappe
from my_app.search import MyAppSearch

@frappe.whitelist()
def search(query, filters=None):
    search = MyAppSearch()
    result = search.search(query, filters=filters)

    return result
```

### 4. Build the Index

Build the search index programmatically or via console:

```python
from my_app.search import MyAppSearch
search = MyAppSearch()
search.build_index()
```

## How It Works

### 1. Indexing Process

#### Full Index Building

When you call `build_index()`, the framework performs a complete index rebuild:

1. **Database Preparation**: Creates a temporary SQLite database with FTS5 tables configured according to your schema
2. **Document Collection**: Queries all specified doctypes using the configured field mappings and filters
3. **Document Processing**: For each document:
   - Extracts and maps fields according to `INDEXABLE_DOCTYPES` configuration
   - Cleans HTML content using BeautifulSoup to extract plain text
   - Applies custom document preparation logic if `prepare_document()` is overridden
   - Validates required fields (title, content) are present
4. **Batch Insertion**: Inserts processed documents into the FTS5 index in batches for performance
5. **Vocabulary Building**: Constructs a spelling correction dictionary from all indexed text
6. **Atomic Replacement**: Replaces the existing index database with the new one atomically

#### Individual Document Indexing

For real-time updates using `index_doc()` or `remove_doc()`:

1. **Single Document Processing**: Retrieves and processes one document using the same field mapping logic
2. **Incremental Update**: Updates the existing FTS5 index by inserting, updating, or deleting the specific document
3. **Vocabulary Update**: Updates the spelling dictionary with new terms from the document

### 2. Search Process

When a user performs a search using `search()`, the framework executes these steps:

1. **Permission Filtering**: Calls `get_search_filters()` to determine what documents the current user can access
2. **Query Preprocessing**:
   - Validates the search query is not empty
   - Combines user-provided filters with permission filters
3. **Spelling Correction**:
   - Analyzes query terms against the vocabulary dictionary
   - Uses trigram similarity to suggest corrections for misspelled words
   - Expands the original query with corrected terms
4. **FTS5 Query Execution**:
   - Constructs an FTS5-compatible query string
   - Executes the full-text search against the SQLite database
   - Applies metadata filters (status, owner, project, etc.)
   - Retrieves raw results with BM25 scores
5. **Results Processing**:
   - **Custom Scoring**: Applies the scoring pipeline to calculate final relevance scores
     - Base BM25 score processing
     - Title matching boosts (exact and partial matches)
     - Recency boosting based on document age
     - Custom scoring functions (doctype-specific, priority-based, etc.)
   - **Ranking**: Sorts results by final scores and assigns rank positions
   - **Content Formatting**: Generates content snippets and highlights matching terms

## Configuration

### INDEX_SCHEMA

Defines the structure of your search index:

```python
INDEX_SCHEMA = {
    # Text fields that will be searchable (defaults to ["title", "content"])
    "text_fields": ["title", "content"],

    # Metadata fields stored alongside text content for filtering
    "metadata_fields": ["project", "owner", "status", "priority"],

    # FTS5 tokenizer configuration
    "tokenizer": "unicode61 remove_diacritics 2 tokenchars '-_@.'"
}
```

### INDEXABLE_DOCTYPES

Specifies which doctypes to index and how to map their fields:

```python
INDEXABLE_DOCTYPES = {
    "Task": {
        # Field mapping
        "fields": [
            "name",
            {"title": "subject"},        # Maps subject field to title
            {"content": "description"},  # Maps description field to content
            {"modified": "creation"},    # Use creation instead of modified for recency boost
            "project",
            "owner"
        ],

        # Optional filters to limit which records are indexed
        "filters": {
            "status": ("!=", "Cancelled"),
            "docstatus": ("!=", 2)
        }
    }
}
```

### Field Mapping Rules

- **String fields**: Direct mapping `"field_name"`
- **Aliased fields**: Dictionary mapping `{"schema_field": "doctype_field"}`
- **Required fields**: `title` and `content` fields must be present or explicitly mapped (e.g., `{"title": "subject"}`)
- **Auto-added fields**: `doctype` and `name` are automatically included
- **Modified field**: Added automatically if used in any doctype configuration. Used for recency boosting - if you want to use a different timestamp field (like `creation` or `last_updated`), map it to `modified` using `{"modified": "creation"}`

## Features & Customization

### Permission Filtering

Implement `get_search_filters()` to control access:

```python
def get_search_filters(self):
    """Return filters based on user permissions"""
    user = frappe.session.user

    if user == "Administrator":
        return {}  # No restrictions

    # Example: User can only see their own and public documents
    return {
        "owner": user,
        "status": ["Active", "Published"]
    }
```

### Custom Scoring

Create custom scoring functions to influence search relevance:

```python
class MyAppSearch(SQLiteSearch):
    ...

    @SQLiteSearch.scoring_function
    def _get_priority_boost(self, row, query, query_words):
        """Boost high-priority items"""
        priority = row.get("priority", "Medium")

        if priority == "High":
            return 1.5
        if priority == "Medium":
            return 1.1
        return 1.0
```

### Recency Boosting

The framework automatically provides time-based recency boosting using the `modified` field:

```python
# The modified field is used for calculating document age
# Recent documents get higher scores:
# - Last 24 hours: 1.8x boost
# - Last 7 days: 1.5x boost
# - Last 30 days: 1.2x boost
# - Last 90 days: 1.1x boost
# - Older documents: gradually decreasing boost

# If your doctype uses a different timestamp field, map it to modified:
INDEXABLE_DOCTYPES = {
    "GP Discussion": {
        "fields": ["name", "title", "content", {"modified": "last_post_at"}, "project"],
    },
    "Article": {
        "fields": ["name", "title", "content", {"modified": "published_date"}, "category"],
    }
}
```

### Document Preparation

Override `prepare_document()` for custom document processing:

```python
def prepare_document(self, doc):
    """Custom document preparation"""
    document = super().prepare_document(doc)
    if not document:
        return None

    # Add computed fields
    if doc.doctype == "Task":
        # Combine multiple fields into content
        content_parts = [
            doc.description or "",
            doc.notes or "",
            "\n".join([comment.content for comment in doc.get("comments", [])])
        ]
        document["content"] = "\n".join(filter(None, content_parts))

        # set fields that might be stored in another table
        document["category"] = get_category_for_task(doc)

    return document
```

### Spelling Correction

The framework includes built-in spelling correction using trigram similarity:

```python
# Spelling correction happens automatically
search_result = search.search("projetc managment")  # Will find "project management"

# Access correction information
print(search_result["summary"]["corrected_words"])
# Output: {"projetc": "project", "managment": "management"}
```

### Content Processing

HTML content is automatically cleaned and processed using BeautifulSoup:

```python
# Complex HTML content like this:
html_content = """
<div class="article">
    <h1>API Documentation</h1>
    <p>Learn how to integrate with our <a href="/api">REST API</a>.</p>
    <img src="/images/api-flow.png" alt="API workflow diagram" />
    <ul>
        <li><strong>Authentication:</strong> Use <code>Bearer tokens</code></li>
        <li>Rate limiting: <em>1000 requests/hour</em></li>
    </ul>
    <blockquote>See our <a href="/examples">code examples</a> for details.</blockquote>
    <table><tr><td>Method</td><td>POST</td></tr></table>
    <script>analytics.track('page_view');</script>
    <style>.hidden { display: none; }</style>
</div>
"""

# Is automatically converted to clean, searchable plain text:
"""
API Documentation

Learn how to integrate with our REST API.

Authentication: Use Bearer tokens
Rate limiting: 1000 requests/hour

See our code examples for details.

Method POST
"""

# The cleaning process:
# 1. Removes all HTML tags (<div>, <h1>, <strong>, <code>, etc.)
# 2. Strips out scripts, styles, and non-content elements
# 3. Extracts link text while removing href URLs
# 4. Normalizes whitespace and line breaks
```

### Title-Only Search

```python
results = search.search("project update", title_only=True)
```

### Advanced Filtering

```python
accessible_projects = ['PROJ001', 'PROJ002', ...]

filters = {
    "project": accessible_projects,     # Multiple values (IN clause)
    "owner": current_user,              # Single value (= clause)
}

results = search.search("bug fix", filters=filters)
```

### Automatic Index Handling

The framework handles index building and maintenance automatically when you register your search class:

```python
# hooks.py
sqlite_search = ['my_app.search.MyAppSearch']
```

**What the framework does automatically:**

1. **Post-Migration Index Building**: Builds the search index automatically after running `bench migrate`
2. **Periodic Index Verification**: Checks every 15 minutes that the index exists and rebuilds if missing
3. **Real-time Document Updates**: Automatically calls `index_doc()` and `remove_doc()` on document lifecycle events (insert, update, delete) for all doctypes defined in your `INDEXABLE_DOCTYPES`

## Manual Index Handling

If you prefer to have manual control over the lifecycle of indexing, then you can simply opt out of automatic index handling by not registering the search class in `sqlite_search` hook.

```python
from my_app.search import MyAppSearch

def build_index_in_background():
    """Manually trigger background index building"""
    search = MyAppSearch()
    if search.is_search_enabled() and not search.index_exists():
        frappe.enqueue("my_app.search.build_index", queue="long")

# hooks.py
scheduler_events = {
    # Custom scheduler (if you want different timing)
    "daily": ["my_app.search.build_index_if_not_exists"],
}
```

## API Reference

#### `search(query, title_only=False, filters=None)`
Main search method that returns formatted results.

**Parameters:**
- `query` (str): Search query text
- `title_only` (bool): Search only in title fields
- `filters` (dict): Additional filters to apply

**Returns:**
```python
{
    "results": [
        {
            "doctype": "Task",
            "name": "TASK-001",
            "title": "Fix login bug",
            "content": "User cannot login after password reset...",
            "score": 0.85,
            "original_rank": 3, # original bm25 rank
            "rank": 1, # modified rank after custom scoring pipeline
            # ... other metadata fields
        }
    ],
    "summary": {
        "duration": 0.023,
        "total_matches": 15,
        "returned_matches": 15,
        "corrected_words": {"loggin": "login"},
        "corrected_query": "Fix login bug",
        "title_only": False,
        "filtered_matches": 15,
        "applied_filters": {"status": ["Open"]}
    }
}
```

#### `build_index()`
Build the complete search index from scratch.

#### `index_doc(doctype, docname)`
Index a single document.

#### `remove_doc(doctype, docname)`
Remove a single document from the index.

#### `is_search_enabled()`
Check if search is enabled (override to add disable logic).

#### `index_exists()`
Check if the search index exists.

#### `get_search_filters()`
**Must be implemented by subclasses.** Return filters for the current user.

**Returns:**
```python
{
    "field_name": "value",           # Single value
    "field_name": ["val1", "val2"],  # Multiple values
}
```


#### `scoring_function()`

Use the `@SQLiteSearch.scoring_function` decorator to mark a function as a scoring function.
