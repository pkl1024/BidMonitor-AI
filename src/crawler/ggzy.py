"""
全国公共资源交易平台爬虫
网站：https://www.ggzy.gov.cn/

2026-08 适配：
- 旧搜索接口 deal.ggzy.gov.cn/ds/deal/dealList_find.jsp 已下线（404/超时）
- 新版搜索接口路径 /information/pubTradingInfo/getTradList 需验证码（code 829 弹 captcha），暂不可用
- 当前可用方案：抓首页"交易公开"最新公告列表（服务端渲染，12条/天）+ 本地关键词过滤
"""
from typing import List, Dict, Any
from urllib.parse import urljoin
from .base import BaseCrawler, BidInfo


class GGZYCrawler(BaseCrawler):
    """全国公共资源交易平台爬虫（首页最新列表版）"""

    name = "ggzy"
    base_url = "https://www.ggzy.gov.cn"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.search_keywords = config.get('search_keywords', ['无人机', '光伏', '风电'])

    def get_list_urls(self) -> List[str]:
        """首页交易公开列表（服务端渲染，含最新公告）"""
        return [f"{self.base_url}/"]

    def parse(self, html: str) -> List[BidInfo]:
        """解析首页交易公开列表"""
        bids = []
        soup = self.parse_html(html)

        # 首页"交易公开"栏目的 ul > li > a + span 日期
        items = soup.select('ul li a[href*="/information/deal/html/"]')

        for title_elem in items:
            try:
                title = title_elem.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                url = title_elem.get('href', '')
                if url and not url.startswith('http'):
                    url = urljoin(self.base_url, url)

                # 日期在 li 内的 span
                publish_date = ""
                li = title_elem.find_parent('li')
                if li:
                    date_elem = li.select_one('span')
                    if date_elem:
                        publish_date = date_elem.get_text(strip=True)

                bids.append(BidInfo(
                    title=title,
                    url=url,
                    publish_date=publish_date,
                    source="全国公共资源交易平台"
                ))
            except Exception as e:
                self.logger.warning(f"Parse error: {e}")
                continue

        # 去重（首页可能有重复入口）
        seen = set()
        unique_bids = []
        for b in bids:
            if b.url not in seen:
                seen.add(b.url)
                unique_bids.append(b)
        return unique_bids
