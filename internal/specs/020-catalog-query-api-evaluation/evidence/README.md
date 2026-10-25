# Local catalog audit outputs

Generated JSON results in this directory are ignored by Git. Existing files
remain on the maintainer's disk; fresh clones contain only this note.
Historical JSON references in the surrounding Markdown identify local artifacts,
not downloadable repository files.

Keep contracts, architecture decisions and concise findings in tracked Markdown.
Put new run journals and measurements under ignored `internal/local/`, rather
than growing the specification into a development log. Archive important local
outputs separately before cleaning a checkout.

JSON consumed by tests belongs in tracked test fixture directories, including
`apps/catalog-worker/tests/fixtures/`. Those fixtures are not ignored by this rule.
