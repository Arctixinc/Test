
import asyncio
from telegraph_helper import TelegraphHelper

async def main():
    # Path to your screenshots folder
    screenshots_dir = "screenshots"

    # Create instance
    telegraph = TelegraphHelper()

    # Create account
    await telegraph.create_account()

    # Upload screenshots and get Telegraph link
    link = await telegraph.upload_screenshots_from_dir(screenshots_dir)
    print(f"Telegraph URL: {link}")

if __name__ == "__main__":
    asyncio.run(main())
    