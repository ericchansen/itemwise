#!/usr/bin/env python
"""Purge E2E test users (e2e-*@test.com) from the database."""

import argparse
import os
import sys

from sqlalchemy import create_engine, text


def main():
    parser = argparse.ArgumentParser(description="Purge E2E test users from the database")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: Set DATABASE_URL environment variable", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Find all E2E test users
        rows = conn.execute(
            text("SELECT id, email FROM users WHERE email LIKE 'e2e-%@test.com' ORDER BY email")
        ).fetchall()

        if not rows:
            print("No E2E test users found.")
            return

        print(f"Found {len(rows)} E2E test user(s):\n")

        plan: list[dict] = []
        for user_id, email in rows:
            # Find inventories where this user is the sole member
            sole_inventories = conn.execute(
                text(
                    "SELECT im.inventory_id FROM inventory_members im "
                    "WHERE im.user_id = :uid "
                    "AND (SELECT COUNT(*) FROM inventory_members WHERE inventory_id = im.inventory_id) = 1"
                ),
                {"uid": user_id},
            ).fetchall()
            sole_inv_ids = [r[0] for r in sole_inventories]

            # Count shared inventory memberships (will just remove membership)
            shared_count_row = conn.execute(
                text(
                    "SELECT COUNT(*) FROM inventory_members im "
                    "WHERE im.user_id = :uid "
                    "AND (SELECT COUNT(*) FROM inventory_members WHERE inventory_id = im.inventory_id) > 1"
                ),
                {"uid": user_id},
            ).fetchone()
            shared_count = shared_count_row[0] if shared_count_row else 0

            plan.append(
                {
                    "user_id": user_id,
                    "email": email,
                    "sole_inventory_ids": sole_inv_ids,
                    "shared_membership_count": shared_count,
                }
            )

            print(f"  {email}")
            print(f"    sole-member inventories to delete: {len(sole_inv_ids)}")
            if shared_count:
                print(f"    shared inventory memberships to remove: {shared_count}")

        if args.dry_run:
            print("\n[DRY RUN] No changes made.")
            return

        # Confirmation
        if not args.yes:
            answer = input("\nProceed with deletion? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted.")
                return

        # Execute deletions
        print("\nDeleting...")
        for entry in plan:
            user_id = entry["user_id"]
            email = entry["email"]

            # Delete sole-member inventories (CASCADE handles items, lots, locations, members)
            for inv_id in entry["sole_inventory_ids"]:
                conn.execute(text("DELETE FROM inventories WHERE id = :inv_id"), {"inv_id": inv_id})

            # Delete the user (CASCADE handles remaining memberships)
            conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})

            print(
                f"  Deleted {email} "
                f"({len(entry['sole_inventory_ids'])} inventories removed)"
            )

        conn.commit()
        print(f"\nDone. Purged {len(plan)} E2E test user(s).")


if __name__ == "__main__":
    main()
