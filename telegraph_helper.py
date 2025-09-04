# telegraph_helper.py

import asyncio
from natsort import natsorted
from os import path as ospath
from aiofiles.os import listdir
from telegraph.upload import upload_file
from secrets import token_hex
from telegraph import Telegraph
from telegraph.exceptions import RetryAfterError
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("Telegraph")

class TelegraphHelper:
    def __init__(self, domain='graph.org'):
        # Telegraph() is synchronous; create the instance now
        self.telegraph = Telegraph(domain=domain)
        self.short_name = token_hex(4)
        self.access_token = None
        self.author_name = 'Arctix'
        self.author_url = 'https://t.me/arctixinc'

    async def create_account(self):
        LOGGER.info("Creating Telegraph Account (in thread)")
        # run blocking create_account in a thread
        result = await asyncio.to_thread(
            self.telegraph.create_account,
            short_name=self.short_name,
            author_name=self.author_name,
            author_url=self.author_url
        )
        # create_account returns a dict; record token if present
        self.access_token = result.get('access_token') or getattr(self.telegraph, 'get_access_token', lambda: None)()
        LOGGER.info(f"Telegraph Account Generated : {self.short_name} (access_token set)")

    async def create_page(self, title, content):
        try:
            # create_page is blocking so run in thread
            page = await asyncio.to_thread(
                self.telegraph.create_page,
                title=title,
                author_name=self.author_name,
                author_url=self.author_url,
                html_content=content
            )
            return page
        except RetryAfterError as st:
            LOGGER.warning(f'Telegraph Flood control exceeded. Sleeping {st.retry_after} seconds.')
            await asyncio.sleep(st.retry_after)
            return await self.create_page(title, content)

    async def safe_upload(self, path, retries=3, delay=2):
        """Upload a file using upload_file (blocking) but run it in a thread and retry asynchronously."""
        for attempt in range(retries):
            try:
                result = await asyncio.to_thread(upload_file, path)
                if isinstance(result, list) and result:
                    return result[0]  # return the file path string
            except Exception as e:
                LOGGER.error(f"Attempt {attempt + 1}: Failed to upload {path}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
        return None

    async def upload_screenshots_from_dir(self, thumbs_dir):
        if not ospath.isdir(thumbs_dir):
            LOGGER.error("Provided directory does not exist.")
            return None

        th_html = "<h4>Screenshots</h4><br>"
        thumbs = await listdir(thumbs_dir)
        for thumb in natsorted(thumbs):
            image_path = ospath.join(thumbs_dir, thumb)
            uploaded_path = await self.safe_upload(image_path)
            if uploaded_path:
                th_html += f'<img src="https://graph.org{uploaded_path}"><br><br>'
                await asyncio.sleep(1)  # slight delay between uploads
            else:
                LOGGER.error(f"Failed to upload {thumb} after retries.")

        page = await self.create_page(title="Screenshots", content=th_html)
        return f"https://graph.org/{page['path']}"
