# telegraph_helper.py (extended)

import asyncio
import json
import requests
from natsort import natsorted
from os import path as ospath
from aiofiles.os import listdir
from secrets import token_hex
from telegraph import Telegraph
from telegraph.exceptions import RetryAfterError
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("Telegraph")


class TelegraphHelper:
    def __init__(self, domain="graph.org", token_file="telegraph_token.json"):
        self.domain = domain
        self.token_file = token_file
        self.telegraph = Telegraph(domain=self.domain)
        self.short_name = token_hex(4)
        self.access_token = None
        self.author_name = "Arctix"
        self.author_url = "https://t.me/arctixinc"

        # Try to load existing token
        self._load_token()

    def _load_token(self):
        if ospath.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    if self.access_token:
                        self.telegraph = Telegraph(
                            domain=self.domain, access_token=self.access_token
                        )
                        LOGGER.info("Loaded existing Telegraph access token.")
            except Exception as e:
                LOGGER.error(f"Failed to load token file: {e}")

    def _save_token(self):
        if self.access_token:
            try:
                with open(self.token_file, "w") as f:
                    json.dump({"access_token": self.access_token}, f)
                LOGGER.info("Telegraph access token saved.")
            except Exception as e:
                LOGGER.error(f"Failed to save token: {e}")

    async def create_account(self):
        if self.access_token:
            LOGGER.info("Using existing Telegraph account.")
            return

        LOGGER.info("Creating new Telegraph account...")
        result = await asyncio.to_thread(
            self.telegraph.create_account,
            short_name=self.short_name,
            author_name=self.author_name,
            author_url=self.author_url,
        )

        self.access_token = result.get("access_token")
        if self.access_token:
            self.telegraph = Telegraph(
                domain=self.domain, access_token=self.access_token
            )
            self._save_token()
            LOGGER.info(
                f"Telegraph Account Generated: {self.short_name} (access_token set)"
            )
        else:
            LOGGER.error("Failed to generate access token!")

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
            LOGGER.warning(
                f"Telegraph Flood control exceeded. Sleeping {st.retry_after} seconds."
            )
            await asyncio.sleep(st.retry_after)
            return await self.create_page(title, content)

    async def upload_to_envs(self, file_path):
        """Upload file to envs.sh and return the public URL."""
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
        except Exception as e:
            LOGGER.critical("envs.sh upload failed: %s", e, exc_info=True)
        return None

    async def upload_screenshots_from_dir(self, thumbs_dir):
        """Upload screenshots to envs.sh and create a Telegraph page with envs.sh links."""
        if not ospath.isdir(thumbs_dir):
            LOGGER.error("Provided directory does not exist.")
            return None

        th_html = "<h4>Screenshots</h4><br>"
        thumbs = await listdir(thumbs_dir)
        for thumb in natsorted(thumbs):
            image_path = ospath.join(thumbs_dir, thumb)
            uploaded_url = await self.upload_to_envs(image_path)
            if uploaded_url:
                th_html += f'<img src="{uploaded_url}"><br><br>'
                await asyncio.sleep(1)
            else:
                LOGGER.error(f"Failed to upload {thumb} to envs.sh")

        page = await self.create_page(title="Screenshots", content=th_html)
        return f"https://{self.domain}/{page['path']}"
