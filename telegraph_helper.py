# telegraph_helper.py

import asyncio
import os
import logging
import requests
from natsort import natsorted
from os import path as ospath
from aiofiles.os import listdir
from telegraph import Telegraph
from telegraph.exceptions import RetryAfterError
from secrets import token_hex
import fitz  # PyMuPDF

# Setup basic logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("Telegraph")


class TelegraphHelper:
    def __init__(self, domain='graph.org'):
        self.telegraph = Telegraph(domain=domain)
        self.short_name = token_hex(4)
        self.access_token = None
        self.author_name = 'Arctix'
        self.author_url = 'https://t.me/arctixinc'

    async def create_account(self):
        LOGGER.info("Creating Telegraph Account (in thread)")
        result = await asyncio.to_thread(
            self.telegraph.create_account,
            short_name=self.short_name,
            author_name=self.author_name,
            author_url=self.author_url
        )
        self.access_token = result.get("access_token")
        if self.access_token:
            self.telegraph = Telegraph(domain="graph.org", access_token=self.access_token)
            LOGGER.info(f"Telegraph Account Generated : {self.short_name} (access_token set)")
        else:
            LOGGER.warning("No access_token received from Telegraph API")

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

    async def safe_upload(self, path, retries=3, delay=2):
        """Upload a file to envs.sh with retries."""
        for attempt in range(retries):
            try:
                with open(path, "rb") as f:
                    files = {"file": f}
                    response = requests.post("https://envs.sh", files=files, timeout=15)
                if response.ok:
                    url = response.text.strip()
                    LOGGER.info("File uploaded to envs.sh: %s", url)
                    return url
                else:
                    LOGGER.error("envs.sh upload failed: %s", response.text)
            except Exception as e:
                LOGGER.error(f"Attempt {attempt + 1}: Failed to upload {path}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
        return None

    async def upload_screenshots_from_dir(self, thumbs_dir):
        """Upload all images from a directory."""
        if not ospath.isdir(thumbs_dir):
            LOGGER.error("Provided directory does not exist.")
            return None

        th_html = "<h3>Report</h3><br>"
        thumbs = await listdir(thumbs_dir)
        for thumb in natsorted(thumbs):
            image_path = ospath.join(thumbs_dir, thumb)
            uploaded_path = await self.safe_upload(image_path)
            if uploaded_path:
                th_html += f'<img src="{uploaded_path}" style="max-width:100%;margin:10px 0;"><br>'
                await asyncio.sleep(1)
            else:
                LOGGER.error(f"Failed to upload {thumb} after retries.")

        page = await self.create_page(title="Screenshots Report", content=th_html)
        return f"https://graph.org/{page['path']}"

    async def upload_from_pdf(self, pdf_url):
        """Download a PDF, extract pages as images using PyMuPDF, upload them, and create a Telegraph page."""
        LOGGER.info(f"Downloading PDF from {pdf_url}")
        response = requests.get(pdf_url)
        pdf_bytes = response.content

        # Extract pages using PyMuPDF
        LOGGER.info("Extracting images from PDF with PyMuPDF...")
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        image_paths = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap()
            img_path = f"page_{i+1}.jpg"
            pix.save(img_path)
            image_paths.append(img_path)

        # Build Telegraph HTML
        th_html = "<h3>PDF Report</h3><br>"
        for img_path in image_paths:
            uploaded_path = await self.safe_upload(img_path)
            if uploaded_path:
                th_html += f'<img src="{uploaded_path}" style="max-width:100%;margin:10px 0;"><br>'
                await asyncio.sleep(1)
            else:
                LOGGER.error(f"Failed to upload {img_path} after retries.")

        page = await self.create_page(title="PDF Report", content=th_html)
        return f"https://graph.org/{page['path']}"
