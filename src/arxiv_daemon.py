"""
此脚本旨在每30分钟左右（例如通过cron定时任务）唤醒一次，
检查是否有通过arxiv API发布的新论文，并将其存储到SQLite数据库中。
"""
import sys,os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/' + '..'))


import sys  # 用于系统退出和参数管理
import time  # 用于睡眠和时间管理
import random  # 用于生成随机等待时间
import logging  # 用于日志记录
import argparse  # 用于解析命令行参数

from util.arxiv_api_client import ArxivAPIClient  # 引入自定义的Arxiv API客户端类
from util.compressed_sqlite_dict_manager import CompressedSqliteDictManager  # 引入自定义的SQLite压缩管理类

# 初始化日志记录器
logging.basicConfig(level=logging.INFO, 
                    format='%(name)s %(levelname)s %(asctime)s %(message)s', 
                    datefmt='%m/%d/%Y %I:%M:%S %p')  # 设置日志输出格式

def store(paper, pdb, mdb):
    """
    将论文和元数据存储到数据库中。
    
    Args:
        paper (dict): 已解析的论文数据
        pdb (CompressedSqliteDict): 论文数据库实例
        mdb (CompressedSqliteDict): 元数据数据库实例
    """
    paper_id = paper['_id']  # 获取论文ID
    pdb[paper_id] = paper  # 将论文数据存入论文数据库
    mdb[paper_id] = {'_time': paper['_time']}  # 将论文元数据存入元数据库

if __name__ == '__main__':
    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description='Arxiv Daemon')  # 创建命令行参数解析器
    parser.add_argument('-n', '--num', type=int, default=100, help='最多获取多少篇论文')  # 设置获取论文数量的参数
    parser.add_argument('-s', '--start', type=int, default=0, help='从哪个索引开始')  # 设置起始索引的参数
    parser.add_argument('-b', '--break-after', type=int, default=3, help='连续多少次无新论文会提前停止？设置为0禁用此功能。')  # 设置提前停止的条件
    args = parser.parse_args()  # 解析命令行参数

    logging.info(f"使用以下参数启动Arxiv Daemon: {args}")  # 输出启动参数的日志

    # Arxiv API 查询字符串，用于搜索新论文
    query = 'cat:cs.CV+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.AI+OR+cat:cs.NE+OR+cat:cs.RO'

    # 初始化API客户端
    arxiv_client = ArxivAPIClient()  # 实例化ArxivAPIClient对象

    # 初始化SQLite数据库管理器，用于论文和元数据
    paper_db_manager = CompressedSqliteDictManager('papers.db')  # 初始化论文数据库管理器
    meta_db_manager = CompressedSqliteDictManager('metas.db')  # 初始化元数据数据库管理器

    # 打开数据库进行读写操作
    pdb = paper_db_manager.get_compressed_db('papers', flag='w')  # 获取论文数据库，写入模式
    mdb = meta_db_manager.get_compressed_db('metas', flag='w')  # 获取元数据数据库，写入模式
    
    prevn = len(pdb)  # 记录当前数据库中已有的论文数量
    total_updated = 0  # 初始化总更新数量
    zero_updates_in_a_row = 0  # 初始化连续0更新次数

    # 从Arxiv API获取最新论文
    for k in range(args.start, args.start + args.num, 100):  # 按每次100篇的步长进行查询
        logging.info(f'正在通过Arxiv API查询"{query}"，起始索引 {k}')  # 输出查询信息的日志

        # 尝试从Arxiv API获取一批论文
        ntried = 0  # 记录尝试次数
        while True:
            try:
                response = arxiv_client.get_papers(query, start_index=k)  # 通过API获取论文
                papers = arxiv_client.parse_response(response)  # 解析API响应的论文数据
                time.sleep(0.5)  # 暂停0.5秒，防止过度请求
                if len(papers) == 100:
                    break  # 当成功获取到100篇论文时，跳出循环
            except Exception as e:
                logging.warning(f"获取论文时出错: {e}")  # 记录警告日志
                logging.warning("稍后将重试...")  # 记录重试日志
                ntried += 1  # 增加重试计数
                if ntried > 1000:
                    logging.error("尝试了1,000次，出现严重问题，程序即将退出。")  # 如果重试次数超过1000次，记录错误日志并退出
                    sys.exit(1)  # 退出程序，返回错误状态码
                time.sleep(2 + random.uniform(0, 4))  # 等待2到4秒之间的随机时间后重试

        # 处理并存储检索到的论文
        nhad, nnew, nreplace = 0, 0, 0  # 初始化计数器：已有论文、新论文、替换论文
        for paper in papers:
            paper_id = paper['_id']  # 获取论文ID
            if paper_id in pdb:
                if paper['_time'] > pdb[paper_id]['_time']:
                    # 如果论文是更新版本，则替换现有论文
                    store(paper, pdb, mdb)  # 存储更新后的论文
                    nreplace += 1  # 增加替换计数
                else:
                    # 该论文已经存在，无需更新
                    nhad += 1  # 增加已有论文计数
            else:
                # 新论文，存入数据库
                store(paper, pdb, mdb)  # 存储新论文
                nnew += 1  # 增加新论文计数
        
        prevn = len(pdb)  # 更新数据库中的论文数量
        total_updated += nreplace + nnew  # 更新总的替换和新增数量

        # 输出进度日志和诊断信息
        logging.info(f"{papers[0]['_time_str']} - 处理结果: 已有={nhad}, 替换={nreplace}, 新增={nnew}. 论文总数: {prevn}")

        # 如果没有新论文，提前退出条件
        if nnew == 0:
            zero_updates_in_a_row += 1  # 连续无新论文次数加1
            if args.break_after > 0 and zero_updates_in_a_row >= args.break_after:
                logging.info(f"连续{args.break_after}次没有新论文，提前退出")  # 记录提前退出日志
                break
            elif k == 0:
                logging.info("第一次调用最新论文没有新结果，退出程序。")  # 如果是第一次调用且无新论文，记录退出日志
                break
        else:
            zero_updates_in_a_row = 0  # 重置连续无更新计数

        # 等待一段随机时间后再发送下一个请求，以避免API限制
        time.sleep(1 + random.uniform(0, 3))  # 随机等待1到3秒之间

    # 如果有更新则以状态码0退出，否则以状态码1退出
    sys.exit(0 if total_updated > 0 else 1)  # 如果有更新则返回0，否则返回1表示无更新