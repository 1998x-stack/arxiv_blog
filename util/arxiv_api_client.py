import sys,os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/' + '..'))

import time
import logging
import urllib.request
from urllib.parse import quote_plus
import feedparser
from collections import OrderedDict
from typing import List, Dict, Tuple, Any

# 初始化日志记录器，用于调试和错误处理
logger = logging.getLogger(__name__)

class ArxivAPIClient:
    """与arXiv API进行交互以获取和处理论文的客户端类。
    
    此类提供查询arXiv API、解析响应以及过滤论文以保留最新版本的方法。
    
    Attributes:
        base_url: arXiv API请求的基础URL。
    """
    
    BASE_URL = 'http://export.arxiv.org/api/query?'
    
    def __init__(self):
        """初始化ArxivAPIClient类。"""
        logger.info("ArxivAPIClient 已初始化")

    def get_papers(self, search_query: str, start_index: int = 0) -> bytes:
        """
        发送请求到arXiv API以获取一批100篇论文。

        Args:
            search_query (str): arXiv API的查询字符串。
            start_index (int): 获取论文的起始索引（默认为0）。

        Returns:
            bytes: 从arXiv API获取的XML格式的原始响应数据。
        
        Raises:
            ValueError: 如果从arXiv API获取的响应无效。
        """
        # Properly encode the search query to avoid spaces and other invalid characters
        encoded_query = quote_plus(search_query)

        query_url = f"{self.BASE_URL}search_query={encoded_query}&sortBy=lastUpdatedDate&start={start_index}&max_results=100"
        logger.debug(f"Querying arXiv with URL: {query_url}")

        try:
            with urllib.request.urlopen(query_url) as url:
                if url.status != 200:
                    raise ValueError("arXiv API returned a non-200 status code.")
                response = url.read()
                return response
        except urllib.error.URLError as e:
            logger.error(f"Failed to connect to arXiv API: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            raise

    def parse_arxiv_url(self, url: str) -> Tuple[str, str, int]:
        """
        解析arXiv URL以提取论文ID和版本。

        Args:
            url (str): arXiv论文的URL。

        Returns:
            Tuple[str, str, int]: 包含完整idv字符串、原始ID和版本号的元组。
        
        Raises:
            ValueError: 如果URL中不包含有效的arXiv ID和版本。
        """
        ix = url.rfind('/')
        if ix < 0:
            raise ValueError(f"URL格式无效: {url}")
        
        idv = url[ix+1:]
        parts = idv.split('v')
        
        if len(parts) != 2:
            raise ValueError(f"在字符串 {idv} 中分割ID和版本失败")
        
        return idv, parts[0], int(parts[1])

    def parse_response(self, response: bytes) -> List[Dict[str, Any]]:
        """
        解析来自arXiv API的响应并返回结构化的论文信息。

        Args:
            response (bytes): arXiv API的原始XML响应。

        Returns:
            List[Dict[str, Any]]: 包含已解析论文数据的字典列表。
        """
        papers = []
        parsed_feed = feedparser.parse(response)
        
        # 遍历解析的条目并提取所需的论文数据
        for entry in parsed_feed.entries:
            paper_data = self._encode_feedparser_dict(entry)
            idv, raw_id, version = self.parse_arxiv_url(paper_data['id'])
            
            paper_data['_idv'] = idv
            paper_data['_id'] = raw_id
            paper_data['_version'] = version
            paper_data['_time'] = time.mktime(paper_data['updated_parsed'])
            paper_data['_time_str'] = time.strftime('%b %d %Y', paper_data['updated_parsed'])
            
            # 删除不必要的详细信息
            paper_data.pop('summary_detail', None)
            paper_data.pop('title_detail', None)
            
            papers.append(paper_data)
        
        return papers

    def _encode_feedparser_dict(self, d: Any) -> Any:
        """
        帮助函数，用于递归地将feedparser对象转换为本地Python类型。

        Args:
            d (Any): feedparser对象或Python字典。

        Returns:
            Any: 本地Python对象。
        """
        if isinstance(d, feedparser.FeedParserDict) or isinstance(d, dict):
            return {k: self._encode_feedparser_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [self._encode_feedparser_dict(i) for i in d]
        return d

    def filter_latest_versions(self, idv_list: List[str]) -> List[str]:
        """
        过滤arXiv ID列表以仅保留每篇论文的最新版本。

        Args:
            idv_list (List[str]): 包含arXiv论文ID及版本（如'1234.5678v2'）的列表。

        Returns:
            List[str]: 包含每篇论文最新版本的arXiv ID列表。
        """
        latest_versions = OrderedDict()
        
        # 遍历所有ID并保留每篇论文的最高版本号
        for idv in idv_list:
            paper_id, version_str = idv.split('v')
            version = int(version_str)
            latest_versions[paper_id] = max(version, latest_versions.get(paper_id, 0))
        
        # 返回最新版本的ID列表
        return [f"{pid}v{v}" for pid, v in latest_versions.items()]

# 使用示例
if __name__ == "__main__":
    client = ArxivAPIClient()
    
    # 示例：查询与“机器学习”相关的论文
    try:
        response = client.get_papers(search_query="machine learning")
        parsed_papers = client.parse_response(response)
        latest_papers = client.filter_latest_versions([paper['_idv'] for paper in parsed_papers])

        # 输出每篇论文的最新版本
        for paper in latest_papers:
            print(f"最新版本: {paper}")
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")