"""
从所有论文摘要中提取TF-IDF特征并将其保存到磁盘。
"""
import sys,os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/' + '..'))


import argparse  # 用于解析命令行参数
from random import shuffle  # 用于随机打乱列表
import numpy as np  # 用于数值计算
from sklearn.feature_extraction.text import TfidfVectorizer  # 用于生成TF-IDF特征
from util.compressed_sqlite_dict_manager import CompressedSqliteDictManager, FeatureStore  # 管理压缩的SQLite数据库 & 管理特征的保存和加载

# -----------------------------------------------------------------------------

if __name__ == '__main__':

    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description='Arxiv TF-IDF 计算器')  # 创建参数解析器
    parser.add_argument('-n', '--num', type=int, default=20000, help='TF-IDF特征数量')  # 设置特征数量的参数
    parser.add_argument('--min_df', type=int, default=5, help='最小文档频率')  # 设置最小文档频率的参数
    parser.add_argument('--max_df', type=float, default=0.1, help='最大文档频率')  # 设置最大文档频率的参数
    parser.add_argument('--max_docs', type=int, default=-1, help='用于训练TF-IDF的最大文档数，-1表示不限制')  # 设置用于训练的最大文档数量
    args = parser.parse_args()  # 解析命令行参数
    print(args)  # 打印参数

    # 初始化TF-IDF向量化器
    vectorizer = TfidfVectorizer(input='content',  # 输入类型为内容文本
                                 encoding='utf-8', decode_error='replace', strip_accents='unicode',  # 编码设置和错误处理
                                 lowercase=True, analyzer='word', stop_words='english',  # 小写化和停用词设置
                                 token_pattern=r'(?u)\b[a-zA-Z_][a-zA-Z0-9_]+\b',  # 词汇的正则表达式
                                 ngram_range=(1, 2), max_features=args.num,  # ngram范围和最大特征数
                                 norm='l2', use_idf=True, smooth_idf=True, sublinear_tf=True,  # 使用IDF并设置平滑和次线性TF
                                 max_df=args.max_df, min_df=args.min_df)  # 文档频率的上下限设置

    # 初始化数据库管理器并打开论文数据库以进行读取
    paper_db_manager = CompressedSqliteDictManager('papers.db')  # 初始化压缩SQLite数据库管理器
    pdb = paper_db_manager.get_compressed_db('papers', flag='r')  # 打开论文数据库，读模式

    def make_corpus(training: bool):
        """
        生成用于训练或推断TF-IDF模型的论文摘要语料库。

        Args:
            training (bool): 如果为True，则根据args.max_docs限制文档数量。
        Yields:
            str: 每篇论文的标题、摘要和作者信息的组合。
        """
        assert isinstance(training, bool)  # 确保training参数是布尔值

        # 确定用于训练TF-IDF的论文集
        if training and args.max_docs > 0 and args.max_docs < len(pdb):
            # 如果是训练模式并且设置了max_docs，则随机选择一部分论文
            keys = list(pdb.keys())  # 获取所有论文的键
            shuffle(keys)  # 随机打乱键列表
            keys = keys[:args.max_docs]  # 截取前max_docs个论文
        else:
            keys = pdb.keys()  # 否则使用所有的论文键

        # 生成论文的摘要（包括标题、摘要和作者名称）
        for paper_id in keys:
            paper_data = pdb[paper_id]  # 从数据库中获取论文数据
            author_str = ' '.join([author['name'] for author in paper_data['authors']])  # 获取所有作者的名字并连接成字符串
            yield ' '.join([paper_data['title'], paper_data['summary'], author_str])  # 生成包含标题、摘要和作者的字符串

    print("正在训练TF-IDF向量...")  # 打印日志信息，表明开始训练
    vectorizer.fit(make_corpus(training=True))  # 使用训练语料库拟合向量化器

    print("正在运行推断...")  # 打印日志信息，表明开始推断
    tfidf_matrix = vectorizer.transform(make_corpus(training=False)).astype(np.float32)  # 对所有文档应用向量化器并生成TF-IDF矩阵
    print(tfidf_matrix.shape)  # 打印TF-IDF矩阵的形状

    # 准备要保存的特征数据字典
    features = {
        'pids': list(pdb.keys()),  # 论文ID列表
        'x': tfidf_matrix,  # TF-IDF矩阵
        'vocab': vectorizer.vocabulary_,  # TF-IDF词汇表
        'idf': vectorizer._tfidf.idf_,  # 向量化器的IDF值
    }

    # 初始化特征存储并将特征保存到磁盘
    feature_store = FeatureStore('features.p')  # 创建FeatureStore实例，目标文件为features.p
    print("正在将特征保存到磁盘...")  # 打印日志信息，表明开始保存
    feature_store.save_features(features)  # 使用FeatureStore保存特征数据