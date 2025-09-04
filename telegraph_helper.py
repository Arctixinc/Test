# telegraph_helper.py

import asyncio
from natsort import natsorted
from os import path as ospath
from aiofiles.os import listdir
from telegraph import Telegraph
from telegraph.upload import upload_file
from telegraph.exceptions import RetryAfterError
from secrets import token_hex
import requests
import datetime
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("Telegraph")


class TelegraphHelper:
    def __init__(self, domain="graph.org"):
        self.domain = domain
        self.telegraph = Telegraph(domain=domain)
        self.short_name = token_hex(4)
        self.access_token = None
        self.author_name = "Arctix"
        self.author_url = "https://t.me/arctixinc"

    async def create_account(self):
        LOGGER.info("Creating Telegraph Account (in thread)")
        result = await asyncio.to_thread(
            self.telegraph.create_account,
            short_name=self.short_name,
            author_name=self.author_name,
            author_url=self.author_url,
        )
        self.access_token = result.get("access_token")
        if self.access_token:
            self.telegraph = Telegraph(access_token=self.access_token, domain=self.domain)
        LOGGER.info(f"Telegraph Account Generated : {self.short_name} (access_token set)")

    async def create_page(self, title, content):
        try:
            page = await asyncio.to_thread(
                self.telegraph.create_page,
                title=title,
                author_name=self.author_name,
                author_url=self.author_url,
                html_content=content,
            )
            return page
        except RetryAfterError as st:
            LOGGER.warning(f"Telegraph Flood control exceeded. Sleeping {st.retry_after} seconds.")
            await asyncio.sleep(st.retry_after)
            return await self.create_page(title, content)

    async def upload_to_envs(self, file_path):
        """Upload a file to envs.sh and return the URL."""
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post("https://envs.sh", files=files, timeout=15)

            if response.ok:
                url = response.text.strip()
                LOGGER.info("File uploaded to envs.sh: %s", url)
                return url
            else:
                LOGGER.error("envs.sh upload failed: %s", response.text)
                return None
        except Exception as e:
            LOGGER.error(f"envs.sh upload error for {file_path}: {e}")
            return None

    async def upload_screenshots_from_dir(self, thumbs_dir):
        """Upload screenshots to envs.sh and create a Telegraph 'News Style' page."""
        if not ospath.isdir(thumbs_dir):
            LOGGER.error("Provided directory does not exist.")
            return None

        today = datetime.datetime.now().strftime("%B %d, %Y")
        th_html = f"""
        <article>
            <header>
                <h2>Latest Screenshots Report</h2>
                <p><em>Published on {today}</em></p>
                <hr>
            </header>
        """

        thumbs = await listdir(thumbs_dir)
        for idx, thumb in enumerate(natsorted(thumbs), start=1):
            image_path = ospath.join(thumbs_dir, thumb)
            uploaded_url = await self.upload_to_envs(image_path)
            if uploaded_url:
                th_html += f"""
                <figure>
                    <img src="{uploaded_url}" alt="Screenshot {idx}">
                    <figcaption>Screenshot {idx}</figcaption>
                </figure>
                <br>
                """
                await asyncio.sleep(1)
            else:
                LOGGER.error(f"Failed to upload {thumb} to envs.sh")

        th_html += f"""
            <footer>
                <hr>
                <p><strong>Author:</strong> {self.author_name} |
                <a href="{self.author_url}">Contact</a></p>
                <p>Powered by Graph.org × envs.sh</p>
            </footer>
        </article>
        """

        page = await self.create_page(title="News Report", content=th_html)
        return f"https://{self.domain}/{page['path']}"
