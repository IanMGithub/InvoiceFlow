import json
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import Base, engine
from app.ingestion import ingest_invoice_file


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/ingest_invoice.py <invoice.json>",
            file=sys.stderr,
        )
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        result = ingest_invoice_file(session, file_path)

    print(json.dumps(result, indent=2))

    if result["status"] in ("ingested", "duplicate"):
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()
