# Local Literature Library

This directory illustrates the library layout for a research project. In an actual
project, store references under that project's `docs/refs/`. This packaged directory
is a format example, not a populated literature collection.

The search helper defaults to `--local-dir ./docs/refs`, relative to its working
directory. Keep metadata, notes and caches together rather than scattering them
across research routes.

```text
docs/refs/
├── index.json               # Versioned PDF metadata index
├── papers/
│   ├── {paper_id}.pdf       # Source PDF, normally excluded from Git
│   ├── {paper_id}.json      # Metadata sidecar
│   └── {paper_id}.md        # Optional extracted text or notes
└── cache/
    └── {source}/
        └── {query_hash}.json
```

## PDF index

Every PDF must have an entry in `index.json`. An unindexed PDF cannot be used as
indexed literature evidence. Version the index so collaborators can inspect the
reference list without downloading all source PDFs.

Run these commands from the skill directory for the packaged example. For a project
library, pass its path to the index helper with `--refs-dir`.

```sh
python3 scripts/refs_index.py
python3 scripts/refs_index.py --check
python3 scripts/refs_index.py --refs-dir path/to/project/docs/refs --check
python3 scripts/refs_index.py --migrate
```

`--check` does not rewrite the index and exits 3 on inconsistency. `--migrate`
converts legacy metadata while retaining fields that still need verification.

The following metadata is illustrative, not a verified paper citation.

```json
{
  "schema": "research-idea-pipeline/refs-index@1",
  "generated_at": "2025-01-01T00:00:00+08:00",
  "count": 1,
  "pdfs": [
    {
      "file": "papers/2401.01234.pdf",
      "paper_id": "2401.01234",
      "title": "Example Paper Title",
      "authors": ["Example Author"],
      "year": 2024,
      "venue": null,
      "arxiv_id": "2401.01234",
      "doi": null,
      "url": "https://arxiv.org/abs/2401.01234",
      "abstract": null,
      "keywords": ["example topic"],
      "pages": 12,
      "size_bytes": 1234567,
      "sha256": "placeholder",
      "added_at": "2025-01-01",
      "source": "arxiv",
      "metadata_from": "sidecar",
      "needs_verification": true,
      "sidecar_path": "papers/2401.01234.json",
      "notes_path": "papers/2401.01234.md"
    }
  ]
}
```

Metadata extraction uses sidecars first, PDF metadata second through `pypdf` or
`pdfinfo`, and filename parsing as a fallback. Filename-derived records have
`metadata_from = "filename"` and `needs_verification = true`.

`file` is the unique key and is relative to the library root. `sha256` detects
replacement of a PDF. Rebuilding preserves `added_at` when file contents are
unchanged. Entries needing verification cannot support novelty claims.

## Sidecar metadata

A sidecar records bibliographic information and provenance. Replace placeholders
with verified metadata before using it as evidence.

```json
{
  "paper_id": "2401.01234",
  "title": "Example Paper Title",
  "authors": ["Example Author"],
  "abstract": "Example abstract text",
  "year": 2024,
  "venue": null,
  "url": "https://arxiv.org/abs/2401.01234",
  "keywords": ["example topic"],
  "source": "local"
}
```

## Populating from Zotero

If a local Zotero library is available, `scripts/zotero_refs.py` exports it into this
layout. It writes metadata sidecars only, by default:

```sh
python3 scripts/zotero_refs.py                 # sidecars into docs/refs/papers/
python3 scripts/zotero_refs.py --link-pdfs     # also symlink PDFs and rebuild index.json
python3 scripts/zotero_refs.py --check         # report drift without writing (exit 3)
```

`--link-pdfs` symlinks the original files from the Zotero storage directory rather than
copying them, and indexes only the PDFs that exist on disk. Pass `--zotero-url` or set
`ZOTERO_LOCAL_API` to point at a non-default Zotero server. Literature search reads
Zotero directly by default and falls back to this directory when the Zotero local API
is unreachable.

## Library rules

Rebuild the index after adding, replacing or deleting PDFs. Retrieval that downloads
a PDF must write its sidecar and rebuild the index in the same step. Keep all index
paths relative so the library remains portable between machines.

Search hits use a `sources` array drawn from `local`, `arxiv`, `openalex` and
`crossref`. Their `source` alias is derived from `sources[0]`. The index's `source`
field instead records the PDF's provenance.

Commit `index.json`. Exclude large PDFs and disposable caches from Git as needed.
For search, override the library location with `--local-dir` or
`RESEARCH_LOCAL_LITERATURE`, and the cache location with `--cache-dir` or
`RESEARCH_LIT_CACHE`. The index helper uses `--refs-dir` for the same library.

See the [literature policy](../../references/literature-policy.md) for source and
verification requirements.
