"""Write the OpenAPI schema to ledger/api/openapi.json (for frontend type generation, e.g. openapi-typescript).

  python3 -m ledger.api.export_openapi [output_path]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    from ledger.api.app import app
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("openapi.json")
    spec = app.openapi()
    out.write_text(json.dumps(spec, indent=1, sort_keys=False) + "\n")
    print(f"wrote {out} ({len(spec['paths'])} paths, {len(spec.get('components', {}).get('schemas', {}))} schemas)")


if __name__ == "__main__":
    main()
