import os
import asyncio
from telegraph_helper import TelegraphHelper

async def main():
    telegraph = TelegraphHelper()
    await telegraph.create_account()

    pdf_url = os.getenv("PDF_URL")
    if pdf_url:
        url = await telegraph.upload_from_pdf(pdf_url)
    else:
        url = await telegraph.upload_screenshots_from_dir("screenshots")

    print(f"Telegraph URL: {url}")

if __name__ == "__main__":
    asyncio.run(main())
    
