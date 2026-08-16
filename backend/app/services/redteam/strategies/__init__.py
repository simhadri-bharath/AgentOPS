"""Red team attack strategies (pluggable per category).

No eager imports. Re-exporting the registry here made importing
`strategies.base` pull the whole registry, and the strategies import
library_loader, which imports base -- a cycle that only fired depending on
which module was imported first. Import `strategies.registry` directly.
"""
