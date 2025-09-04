# telegraph_helper.py

import asyncio
import re
from natsort import natsorted
from os import path as ospath
from aiofiles.os import listdir
from telegraph import Telegraph
from telegraph.exceptions import RetryAfterError
from secrets import token_hex
import requests
import datetime
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("Telegraph")


class TelegraphHelper:
    def __init__(self, domain='graph.org', token_file='telegraph_token.json'):
        self.domain = domain
        self.telegraph = Telegraph(domain=domain)
        self.short_name = token_hex(4)
        self.access_token = None
        self.author_name = 'Arctix'
        self.author_url = 'https://t.me/arctixinc'
        self.token_file = token_file

        # try to load saved token
        try:
            import json
            if ospath.exists(self.token_file):
                with open(self.token_file, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    if self.access_token:
                        self.telegraph = Telegraph(domain=self.domain, access_token=self.access_token)
                        LOGGER.info("Loaded existing Telegraph access token.")
        except Exception:
            pass

    async def create_account(self):
        if self.access_token:
            LOGGER.info("Using existing Telegraph account.")
            return

        LOGGER.info("Creating Telegraph Account (in thread)")
        result = await asyncio.to_thread(
            self.telegraph.create_account,
            short_name=self.short_name,
            author_name=self.author_name,
            author_url=self.author_url
        )
        self.access_token = result.get("access_token")
        if self.access_token:
            self.telegraph = Telegraph(access_token=self.access_token, domain=self.domain)
            # persist token
            try:
                import json
                with open(self.token_file, "w") as f:
                    json.dump({"access_token": self.access_token}, f)
                LOGGER.info("Telegraph access token saved to %s", self.token_file)
            except Exception as e:
                LOGGER.warning("Failed to save token file: %s", e)
        LOGGER.info(f"Telegraph Account Generated : {self.short_name} (access_token set)")

    async def create_page(self, title, content):
        try:
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
        """Upload screenshots to envs.sh and create a Telegraph page with simple clean style."""
        if not ospath.isdir(thumbs_dir):
            LOGGER.error("Provided directory does not exist.")
            return None

        if not self.access_token:
            await self.create_account()

        thumbs = await listdir(thumbs_dir)
        thumbs = natsorted(thumbs)

        th_html = []
        uploaded_count = 0

        for thumb in thumbs:
            image_path = ospath.join(thumbs_dir, thumb)
            if not ospath.isfile(image_path):
                continue

            uploaded_url = await self.upload_to_envs(image_path)
            if uploaded_url:
                # Only the image, no filename, no "Screenshot X"
                th_html.append(f'<p><img src="{uploaded_url}"></p>')
                th_html.append("<br>")
                uploaded_count += 1
                await asyncio.sleep(1)
            else:
                LOGGER.error(f"Failed to upload {thumb} to envs.sh")

        # Add footer with date and credit
        today = datetime.datetime.now().strftime("%B %d, %Y")
        th_html.append(f'<p><em>Published on {today}</em></p>')
        th_html.append(f'<p><strong>{self.author_name}</strong> — <a href="{self.author_url}">Contact</a></p>')

        if uploaded_count == 0:
            LOGGER.error("No screenshots uploaded successfully; not creating page.")
            return None

        content = "\n".join(th_html)
        page = await self.create_page(title="Screenshots Gallery", content=content)
        return f"https://{self.domain}/{page['path']}"
