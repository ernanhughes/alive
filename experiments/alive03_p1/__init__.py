"""ALIVE-03-P1 harness (canonical research home).

The frozen implementation currently remains under ``alive/experiment/`` with
byte-identical sources pinned by ``benchmarks/alive03-p1/freeze-*.json``.
That placement is legacy: the freeze manifest hashes those exact paths, so a
physical move requires an explicit re-seal and must never silently rewrite
historical artifacts.

New research code for this study belongs here and must import the runtime via
``alive.governance`` / ``alive.*``. Nothing under ``alive/`` may import this
package (enforced by ``tests/test_arch_boundaries.py``).
"""

__all__ = []
