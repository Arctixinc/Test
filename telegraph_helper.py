# telegraph_helper.py
import asyncio
from natsort import natsorted
from os import path as ospath
from aiofiles.os import listdir
from telegraph.upload import upload_file
from secrets import token_hex
from telegraph.aio import Telegraph
from telegraph.exceptions import RetryAfterError
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("Telegraph")

class TelegraphHelper:
    def __init__(self):
        self.telegraph = Telegraph(domain='graph.org')
        self.short_name = token_hex(4)
        self.access_token = None
        self.author_name = 'Arctix'
        self.author_url = 'https://t.me/arctixinc'

    async def create_account(self):
        LOGGER.info("Creating Telegraph Account")
        await self.telegraph.create_account(
            short_name=self.short_name,
            author_name=self.author_name,
            author_url=self.author_url
        )
        self.access_token = self.telegraph.get_access_token()
        LOGGER.info(f"Telegraph Account Generated : {self.short_name}")

    async def create_page(self, title, content):
        try:
            return await self.telegraph.create_page(
                title=title,
                author_name=self.author_name,
                author_url=self.author_url,
                html_content=content
            )
        except RetryAfterError as st:
            LOGGER.warning(f'Telegraph Flood control exceeded. Sleeping {st.retry_after} seconds.')
            await asyncio.sleep(st.retry_after)
            return await self.create_page(title, content)

    async def upload_screenshots_from_dir(self, thumbs_dir):
        if not ospath.isdir(thumbs_dir):
            LOGGER.error("Provided directory does not exist.")
            return None

        th_html = "<h4>Screenshots</h4><br>"
        thumbs = await listdir(thumbs_dir)
        for thumb in natsorted(thumbs):
            image_path = ospath.join(thumbs_dir, thumb)
            try:
                uploaded = upload_file(image_path)
                th_html += f'<img src="https://graph.org{uploaded[0]}"><br><br>'
            except Exception as e:
                LOGGER.error(f"Failed to upload {thumb}: {e}")

        page = await self.create_page(title="Screenshots", content=th_html)
        return f"https://graph.org/{page['path']}"
        