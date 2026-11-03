from sqlalchemy.orm import Session

from app.db import PROJECT_DIR, Base, engine
from app.reference_data import seed_reference_data


def main():
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        with session.begin():
            seed_reference_data(session, PROJECT_DIR, echo=True)


if __name__ == "__main__":
    main()
