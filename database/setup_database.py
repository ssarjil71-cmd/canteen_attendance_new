#!/usr/bin/env python3

from database.bootstrap import ensure_database_ready


def main():
    print("🚀 Syncing MySQL schema...")
    success = ensure_database_ready()
    if success:
        print("✅ MySQL schema is ready and up to date.")
        return True

    print("❌ MySQL schema sync failed.")
    return False


if __name__ == "__main__":
    main()