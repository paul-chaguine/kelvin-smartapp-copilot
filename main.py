import asyncio

from kelvin.application import KelvinApp


async def main() -> None:
    app = KelvinApp()

    await app.connect()

    while True:
        # Custom Loop
        print("My APP is running!")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
