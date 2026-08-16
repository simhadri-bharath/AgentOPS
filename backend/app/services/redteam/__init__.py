"""Red team security scanning.

No eager imports: re-exporting the runners here pulls the invoker during
package init, which is how the evaluation package ended up with an import
cycle. Import the modules directly instead.
"""
