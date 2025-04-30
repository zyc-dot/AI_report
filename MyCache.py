import os
import pickle
import random


class SemanticCache:
    """长期语义缓存类，同时缓存SQL和ECharts代码"""

    def __init__(self, cache_file='semantic_cache_cm_dashboard.pkl'):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self):
        """从磁盘加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except (EOFError, pickle.UnpicklingError):
                return {}
        return {}

    def get(self, key):
        """获取缓存，返回(sql, echarts_code)元组"""
        return self.cache.get(key)

    def set(self, key, sql, echarts_code):
        """设置缓存并持久化到磁盘"""
        self.cache[key] = (sql, echarts_code)
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.cache, f)
