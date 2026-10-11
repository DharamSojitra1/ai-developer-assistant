import asyncio

from app.database import (
    connect_to_mongodb,
    close_mongodb_connection,
    set_user_role,
)


async def main():
    email = input("Enter the existing user's email: ").strip().lower()

    if not email:
        print("Email cannot be empty.")
        return

    await connect_to_mongodb()

    try:
        updated = await set_user_role(
            email=email,
            role="admin",
        )

        if updated:
            print(f"Successfully promoted {email} to admin.")
        else:
            print("No user found with that email.")
    finally:
        await close_mongodb_connection()


if __name__ == "__main__":
    asyncio.run(main())