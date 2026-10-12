from sqlalchemy.orm import Session

from app.db import engine
from app.matching import match_vendor


def main():
    supplier_names = [
        "Northstar Office Supply",
        "Northstar Office Supply LLC",
        "  NORTHSTAR OFFICE SUPPLY  ",
        "Unknown Supplier",
    ]

    with Session(engine) as session:
        for supplier_name in supplier_names:
            result = match_vendor(session, supplier_name)
            print(f"{supplier_name!r} -> {result}")


if __name__ == "__main__":
    main()
