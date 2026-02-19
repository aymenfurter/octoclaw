"""Resolve Key Vault references and emit ``export`` statements.

Called by ``entrypoint.sh`` as::

    eval "$(python -m polyclaw.keyvault_resolve)"

Reads ``@kv:`` references from ``os.environ``, resolves them via
:class:`~app.runtime.services.keyvault.KeyVaultClient`, and prints
``export KEY=value`` lines to stdout so the calling shell can
set the real values **before** the main process starts.
"""

from __future__ import annotations

import os
import shlex
import sys


def main() -> None:
    from .services.keyvault import is_kv_ref, kv

    if not kv.enabled:
        return

    refs: dict[str, str] = {}
    for key, value in os.environ.items():
        if is_kv_ref(value):
            refs[key] = value

    if not refs:
        return

    resolved = kv.resolve(refs)
    for key, value in resolved.items():
        print(f"export {key}={shlex.quote(value)}")

    print(
        f"echo 'Resolved {len(resolved)} secret(s) from Key Vault.'",
        file=sys.stdout,
    )


if __name__ == "__main__":
    main()
