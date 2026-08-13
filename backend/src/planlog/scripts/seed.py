"""Bootstrap first admin user."""

import sys

from sqlmodel import Session, select

from planlog.auth import generate_api_key, hash_api_key
from planlog.db import engine
from planlog.models import User


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "Admin"
    email = sys.argv[2] if len(sys.argv) > 2 else "admin@planlog.local"

    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            print(f"User already exists: {email}")
            sys.exit(0)

        api_key = generate_api_key()
        user = User(name=name, email=email, api_key_hash=hash_api_key(api_key))
        session.add(user)
        session.commit()
        print(f"Created user: {name} <{email}>")
        print(f"API key (save this — shown once): {api_key}")


if __name__ == "__main__":
    main()
