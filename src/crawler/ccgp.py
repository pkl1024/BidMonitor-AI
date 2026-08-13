"""
中国政府采购网爬虫 - 搜索接口版
网站：https://www.ccgp.gov.cn/
搜索接口：https://search.ccgp.gov.cn/bxsearch

2026-08 适配：
- 搜索接口需先访问主站拿 cookie，再带 Referer 请求，否则 403/频繁访问
- 使用 https（http 会被 301 且可能被风控）
- 结果页结构：ul.vT-srch-result-list-bid > li > a(标题) + p(摘要) + 日期
"""
import re
from typing import List, Dict, Any
from urllib.parse import urljoin, quote
from datetime import datetime, timedelta

from .base import BaseCrawler, BidInfo


class CCGPCrawler(BaseCrawler):
    """中国政府采购网爬虫（搜索接口版）"""

    name = "ccgp"
    base_url = "https://www.ccgp.gov.cn"
    search_base = "https://search.ccgp.gov.cn"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.search_keywords = config.get('search_keywords', ['数控加工', 'CNC加工', '机加工'])
        self.search_days = config.get('search_days', 7)

    def _init_session_cookie(self):
        """先访问主站拿 cookie，避免搜索接口风控"""
        try:
            self.session.get(
                "https://www.ccgp.gov.cn/",
                headers=self._get_headers(),
                timeout=self.timeout,
                verify=False,
            )
        except Exception:
            pass  # cookie 拿不到也不致命，尽力而为

    def get_list_urls(self) -> List[str]:
        """生成搜索 URL 列表（按关键词 + 近 N 天）"""
        self._init_session_cookie()
        end = datetime.now()
        start = end - timedelta(days=self.search_days)
        start_str = start.strftime("%Y:%m:%d")
        end_str = end.strftime("%Y:%m:%d")

        urls = []
        for keyword in self.search_keywords:
            url = (
                f"{self.search_base}/bxsearch?searchtype=1&page_index=1&bidSort=0"
                f"&buyerName=&projectId=&pinMu=0&bidType=0&dbselect=bidx"
                f"&kw={quote(keyword)}&start_time={start_str}&end_time={end_str}"
                f"&timeType=6&displayZone=&zoneId=&pppStatus=0&agentName="
            )
            urls.append(url)
        return urls

    def _fetch_with_cookie(self, url: str) -> str:
        """带 cookie + Referer 抓取，返回 HTML"""
        response = self.session.get(
            url,
            headers={
                **self._get_headers(),
                "Referer": "https://www.ccgp.gov.cn/",
            },
            timeout=self.timeout,
            verify=False,
            allow_redirects=True,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response.text

    def crawl(self, stop_event=None) -> List[BidInfo]:
        """重写 crawl：搜索接口走自己的 fetch 逻辑（带 cookie 会话）"""
        all_bids = []
        urls = self.get_list_urls()
        self.logger.info(f"[{self.name}] Starting crawl, {len(urls)} search page(s)")

        for url in urls:
            if stop_event and stop_event.is_set():
                break
            try:
                html = self._fetch_with_cookie(url)
                if html:
                    bids = self.parse(html)
                    all_bids.extend(bids)
                    self.logger.info(f"[{self.name}] Got {len(bids)} items from {url[:120]}")
            except Exception as e:
                self.logger.warning(f"[{self.name}] Failed {url[:120]}: {e}")

        self.logger.info(f"[{self.name}] Crawl done, got {len(all_bids)} items total")
        return all_bids

    def parse(self, html: str) -> List[BidInfo]:
        """解析搜索结果页"""
        bids = []
        soup = self.parse_html(html)

        # 新版搜索结果结构
        items = soup.select('ul.vT-srch-result-list-bid li')
        if not items:
            # 兜底：任何 li > a 结构
            items = soup.select('div.vT-srch-result-list li')

        for item in items:
            try:
                title_elem = item.select_one('a')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                # 去掉 <font color=red> 高亮标签干扰
                title = re.sub(r'\s+', ' ', title).strip()
                if not title or len(title) < 10:
                    continue

                url = title_elem.get('href', '')
                if url and not url.startswith('http'):
                    url = urljoin(self.base_url, url)

                # 日期：li 尾部文本里的 YYYY.MM.DD
                publish_date = ""
                li_text = item.get_text(" ", strip=True)
                m = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', li_text)
                if m:
                    publish_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

                bids.append(BidInfo(
                    title=title,
                    url=url,
                    publish_date=publish_date,
                    source="中国政府采购网"
                ))
            except Exception as e:
                self.logger.warning(f"Parse item error: {e}")
                continue

        return bids
