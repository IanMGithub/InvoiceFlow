import json

from sqlalchemy.orm import Session

from app.db import PROJECT_DIR, Base, engine
from app.invoice_processing import process_invoice


def main():
    Base.metadata.create_all(engine)

    fixture_path = (
        PROJECT_DIR / "fixtures" / "invoices" / "valid_invoice.json"
    )

    with fixture_path.open(encoding="utf-8") as file:
        invoice = json.load(file)

    with Session(engine) as session:
        result = process_invoice(session, invoice)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
