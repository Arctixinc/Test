import asyncio
from telegraph_helper import TelegraphHelper

async def main():
    telegraph = TelegraphHelper()
    await telegraph.create_account()
    url = await telegraph.upload_screenshots_from_dir("screenshots")
    print(f"Telegraph URL: {url}")

if __name__ == "__main__":
    asyncio.run(main())
