import sys,os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/' + '..'))

import os
import sqlite3
import zlib
import pickle
import tempfile
from contextlib import contextmanager
from typing import Dict, Any, Generator
from sqlitedict import SqliteDict
import logging

# 设置日志记录器
logger = logging.getLogger(__name__)

# 全局配置，指定数据存储目录
DATA_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__) + '/' + '..'), 'data'
    )
PAPERS_DB_FILE = os.path.join(DATA_DIR, 'papers.db')
DICT_DB_FILE = os.path.join(DATA_DIR, 'dict.db')
FEATURES_FILE = os.path.join(DATA_DIR, 'features.p')

# -----------------------------------------------------------------------------

class AtomicFileWriter:
    """
    原子文件写入类，确保文件写入操作的原子性。
    
    Attributes:
        dir_path (str): 文件写入的目录路径
    """

    def __init__(self, dir_path: str):
        """
        初始化 AtomicFileWriter 实例，指定文件目录。

        Args:
            dir_path (str): 文件存储的目录路径
        """
        self.dir_path = dir_path

    @contextmanager
    def _tempfile(self, *args, **kwargs) -> Generator[str, None, None]:
        """
        临时文件上下文管理器，负责安全的文件写入操作。
        在上下文退出时会自动删除临时文件。

        Args:
            args, kwargs: 传递给 tempfile.mkstemp 的参数
        Yields:
            str: 临时文件的路径
        """
        fd, temp_path = tempfile.mkstemp(*args, dir=self.dir_path, **kwargs)
        try:
            yield temp_path
        finally:
            try:
                os.remove(temp_path)
            except OSError as e:
                if e.errno != 2:
                    raise e

    @contextmanager
    def open_atomic(self, filepath: str, *args, **kwargs) -> Generator[Any, None, None]:
        """
        安全的文件写入上下文管理器，临时文件写入后原子移动到目标路径。
        支持文件同步（fsync）。

        Args:
            filepath (str): 目标文件路径
            args, kwargs: 传递给 open() 函数的参数
        Yields:
            文件对象
        """
        fsync = kwargs.pop('fsync', False)
        with self._tempfile() as temp_path:
            with open(temp_path, *args, **kwargs) as f:
                yield f
                if fsync:
                    f.flush()
                    os.fsync(f.fileno())
            os.rename(temp_path, filepath)
        logger.info(f"成功将文件原子性写入: {filepath}")

    def safe_pickle_dump(self, obj: Any, filename: str) -> None:
        """
        安全地将对象序列化为pickle并存储到文件中，确保原子性。

        Args:
            obj (Any): 需要序列化的对象
            filename (str): 目标文件名
        """
        with self.open_atomic(filename, 'wb') as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"对象已成功保存为pickle文件: {filename}")

# -----------------------------------------------------------------------------

class CompressedSqliteDictManager:
    """
    管理压缩的SQLite数据库访问，支持数据压缩和解压缩。
    
    Methods:
        get_compressed_db: 获取压缩数据库实例
    """

    class CompressedSqliteDict(SqliteDict):
        """ 压缩版SqliteDict，负责使用zlib进行数据的压缩和解压缩。 """
        @staticmethod
        def encode(obj: Any) -> sqlite3.Binary:
            """ 压缩并序列化对象 """
            return sqlite3.Binary(zlib.compress(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)))

        @staticmethod
        def decode(obj: bytes) -> Any:
            """ 解压缩并反序列化对象 """
            return pickle.loads(zlib.decompress(obj))

    def __init__(self, db_file: str):
        """
        初始化 CompressedSqliteDictManager，指定数据库文件路径。

        Args:
            db_file (str): 数据库文件路径
        """
        self.db_file = db_file

    def get_compressed_db(self, table_name: str, flag: str = 'w', autocommit: bool = True) -> CompressedSqliteDict:
        """
        获取压缩数据库实例。

        Args:
            table_name (str): 数据库表名
            flag (str): 打开模式，'r'表示只读，'w'表示读写
            autocommit (bool): 是否自动提交变更

        Returns:
            CompressedSqliteDict: 数据库实例
        """
        assert flag in ['r', 'w'], "flag参数必须为'r'或'w'"
        logger.info(f"打开压缩数据库, 模式: {flag}, 表: {table_name}")
        return self.CompressedSqliteDict(self.db_file, tablename=table_name, flag=flag, autocommit=autocommit)

# -----------------------------------------------------------------------------

class FeatureStore:
    """
    特征存储类，用于保存和加载特征数据到pickle文件中。
    
    Attributes:
        feature_file (str): 用于存储特征数据的文件路径
    """

    def __init__(self, feature_file: str):
        """
        初始化 FeatureStore，指定特征文件路径。

        Args:
            feature_file (str): 用于存储特征数据的文件路径
        """
        self.feature_file = feature_file
        self.atomic_writer = AtomicFileWriter(os.path.dirname(feature_file))

    def save_features(self, features: Dict[str, Any]) -> None:
        """
        将特征数据保存到pickle文件。

        Args:
            features (Dict[str, Any]): 特征数据字典
        """
        logger.info(f"保存特征数据到文件: {self.feature_file}")
        self.atomic_writer.safe_pickle_dump(features, self.feature_file)

    def load_features(self) -> Dict[str, Any]:
        """
        从pickle文件中加载特征数据。

        Returns:
            Dict[str, Any]: 特征数据字典
        """
        if not os.path.exists(self.feature_file):
            logger.error(f"特征文件不存在: {self.feature_file}")
            raise FileNotFoundError(f"特征文件 {self.feature_file} 不存在")
        
        logger.info(f"加载特征数据从文件: {self.feature_file}")
        with open(self.feature_file, 'rb') as f:
            features = pickle.load(f)
        return features


# ------------------------------------------------

# -----------------------------------------------------------------------------
"""
some docs to self:
flag='c': default mode, open for read/write, and creating the db/table if necessary
flag='r': open for read-only
"""

# stores info about papers, and also their lighter-weight metadata
PAPERS_DB_FILE = os.path.join(DATA_DIR, 'papers.db')
# stores account-relevant info, like which tags exist for which papers
DICT_DB_FILE = os.path.join(DATA_DIR, 'dict.db')

def get_papers_db(flag='r', autocommit=True):
    assert flag in ['r', 'c']
    pdb = CompressedSqliteDict(PAPERS_DB_FILE, tablename='papers', flag=flag, autocommit=autocommit)
    return pdb

def get_metas_db(flag='r', autocommit=True):
    assert flag in ['r', 'c']
    mdb = SqliteDict(PAPERS_DB_FILE, tablename='metas', flag=flag, autocommit=autocommit)
    return mdb

def get_tags_db(flag='r', autocommit=True):
    assert flag in ['r', 'c']
    tdb = CompressedSqliteDict(DICT_DB_FILE, tablename='tags', flag=flag, autocommit=autocommit)
    return tdb

def get_last_active_db(flag='r', autocommit=True):
    assert flag in ['r', 'c']
    ladb = SqliteDict(DICT_DB_FILE, tablename='last_active', flag=flag, autocommit=autocommit)
    return ladb

def get_email_db(flag='r', autocommit=True):
    assert flag in ['r', 'c']
    edb = SqliteDict(DICT_DB_FILE, tablename='email', flag=flag, autocommit=autocommit)
    return edb

# -----------------------------------------------------------------------------
"""
our "feature store" is currently just a pickle file, may want to consider hdf5 in the future
"""

# stores tfidf features a bunch of other metadata
FEATURES_FILE = os.path.join(DATA_DIR, 'features.p')

def save_features(features):
    """ takes the features dict and save it to disk in a simple pickle file """
    safe_pickle_dump(features, FEATURES_FILE)

def load_features():
    """ loads the features dict from disk """
    with open(FEATURES_FILE, 'rb') as f:
        features = pickle.load(f)
    return features


# -----------------------------------------------------------------------------
# Example usage of the above classes
if __name__ == "__main__":
    # Example of using the database manager
    db_manager = CompressedSqliteDictManager(PAPERS_DB_FILE)
    papers_db = db_manager.get_compressed_db('papers', flag='c')

    # Example of using the feature store
    feature_store = FeatureStore(FEATURES_FILE)
    
    # Save and load features
    example_features = {'paper1': [0.1, 0.2, 0.3]}
    feature_store.save_features(example_features)
    loaded_features = feature_store.load_features()

    print(loaded_features)