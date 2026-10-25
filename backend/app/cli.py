"""AMRIN backend management commands."""

import argparse
from getpass import getpass
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.session import build_engine, build_session_factory
from app.models import User
from app.schemas.auth import CreateAdminRequest
from app.services.demo_seed import seed_demo
from app.security.passwords import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=["seed-demo", "create-admin"])
    args = parser.parse_args()

    engine = build_engine(Settings().database_url)
    session_factory = build_session_factory(engine)
    try:
        if args.command == "seed-demo":
            with session_factory.begin() as session:
                counts = seed_demo(session)
            inserted = sum(counts.values())
            print(f"Demo seed complete: {inserted} records inserted across {len(counts)} record types.")
        else:
            _create_admin(session_factory)
    finally:
        engine.dispose()


def _create_admin(session_factory) -> None:
    with session_factory() as session:
        if session.scalar(select(User.id).where(User.role == "admin")):
            raise SystemExit("An administrator already exists; refusing to create another through this first-admin command.")
    print("Create the first AMRIN administrator. The password will not be displayed.")
    name = input("Name: ").strip()
    email = input("Email: ").strip().lower()
    username = input("Username: ").strip().lower()
    password = getpass("Password (12+ characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")
    try:
        values = CreateAdminRequest(name=name, email=email, username=username, password=password)
    except ValidationError as exc:
        raise SystemExit(f"Invalid administrator details: {exc}") from exc

    with session_factory.begin() as session:
        if session.scalar(select(User.id).where(User.role == "admin")):
            raise SystemExit("An administrator already exists; refusing to create another through this first-admin command.")
        user = User(
            id=f"USER-{uuid4().hex}",
            name=values.name.strip(),
            email=str(values.email).strip().lower(),
            username=values.username.strip().lower(),
            password_hash=hash_password(values.password),
            role="admin",
            approval_status="approved",
            city=None,
            worker_id=None,
            is_active=True,
            source="cli",
        )
        session.add(user)
        try:
            session.flush()
        except IntegrityError as exc:
            raise SystemExit("That email or username is already in use.") from exc
    print(f"Administrator account created for {values.email}.")


if __name__ == "__main__":
    main()
