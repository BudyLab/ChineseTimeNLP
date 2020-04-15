from typing import List

import arrow
from loguru import logger

from .helpers.str_common import (
    del_keyword,
    number_translator,
    filter_irregular_expression,
)
from .point import TimePoint
from .unit import TimeUnit


# 时间表达式识别的主要工作类
class TimeNormalizer:
    def __init__(self, isPreferFuture=True, pattern=None):
        self.isPreferFuture = isPreferFuture
        if pattern is None:
            from .resource.pattern import pattern

        self.pattern = pattern

    def parse(self, target: str, baseTime=None) -> dict:
        """
        TimeNormalizer的构造方法，baseTime取默认的系统当前时间
        :param baseTime: 基准时间点
        :param target: 待分析字符串
        :return: 时间单元数组
        """
        if baseTime is None:
            baseTime = arrow.now("Asia/Shanghai")

        logger.debug(f"目标字符串: {target}")

        self.isTimeSpan = False
        self.invalidSpan = False
        self.timeSpan = ""
        self.target = target
        self.baseTime = baseTime
        self.__preHandling()
        self.timeToken = self.__timeEx()
        dic = {}
        res = self.timeToken
        if self.isTimeSpan:
            if self.invalidSpan:
                dic["type"] = "error"
                dic["error"] = "no time pattern could be extracted."
            else:
                result = {}
                dic["type"] = "timedelta"
                dic["timedelta"] = self.timeSpan
                logger.debug(f"timedelta: {dic['timedelta']}")
                index = dic["timedelta"].find("days")
                days = int(dic["timedelta"][: index - 1])
                result["year"] = int(days / 365)
                result["month"] = int(days / 30 - result["year"] * 12)
                result["day"] = int(days - result["year"] * 365 - result["month"] * 30)
                index = dic["timedelta"].find(",")
                time = dic["timedelta"][index + 1 :]
                time = time.split(":")
                result["hour"] = int(time[0])
                result["minute"] = int(time[1])
                result["second"] = int(time[2])
                dic["timedelta"] = result
        else:
            if len(res) == 0:
                dic["type"] = "error"
                dic["error"] = "no time pattern could be extracted."
            elif len(res) == 1:
                dic["type"] = "timestamp"
                dic["timestamp"] = res[0].time.format("YYYY-MM-DD HH:mm:ss")
            else:
                dic["type"] = "timespan"
                dic["timespan"] = [
                    res[0].time.format("YYYY-MM-DD HH:mm:ss"),
                    res[1].time.format("YYYY-MM-DD HH:mm:ss"),
                ]
        return dic

    def __preHandling(self):
        """
        待匹配字符串的清理空白符和语气助词以及大写数字转化的预处理
        :return:
        """
        self.target = filter_irregular_expression(self.target)
        self.target = del_keyword(self.target, r"\s+")  # 清理空白符
        self.target = del_keyword(self.target, "[的]+")  # 清理语气助词
        self.target = number_translator(self.target)  # 大写数字转化
        logger.debug(f"清理空白符和语气助词以及大写数字转化的预处理 {self.target}")

    def __timeEx(self) -> List[TimeUnit]:
        """
        :return: TimeUnit[]时间表达式类型数组
        """
        startline = -1
        endline = -1
        rpointer = 0
        temp = []

        match = self.pattern.finditer(self.target)
        logger.debug("=======")
        logger.debug("用正则提取关键字：")
        for m in match:
            logger.debug(m)
            startline = m.start()
            if startline == endline:
                rpointer -= 1
                temp[rpointer] = temp[rpointer] + m.group()
            else:
                temp.append(m.group())
            logger.debug(f"temp：{temp}")
            endline = m.end()
            rpointer += 1
        logger.debug("=======")

        res: List[TimeUnit] = []
        # 时间上下文： 前一个识别出来的时间会是下一个时间的上下文，用于处理：周六3点到5点这样的多个时间的识别，第二个5点应识别到是周六的。
        contextTp = TimePoint()

        logger.debug(f"基础时间 {self.baseTime}")
        logger.debug(f"待处理的字段: {temp}")
        logger.debug(f"rpointer: {rpointer}")
        for i in range(0, rpointer):
            # 这里是一个类嵌套了一个类
            res.append(TimeUnit(temp[i], self, contextTp))
            contextTp = res[i].tp

        logger.debug(f"时间表达式类型数组 {res}")
        res = self.__filterTimeUnit(res)
        return res

    def __filterTimeUnit(self, tu_arr: List[TimeUnit]):
        """
        过滤timeUnit中无用的识别词。无用识别词识别出的时间是1970.01.01 00:00:00(fastTime=0)
        :return:
        """
        if (tu_arr is None) or (len(tu_arr) < 1):
            return tu_arr
        res = []
        for tu in tu_arr:
            if tu.time.timestamp != 0:
                res.append(tu)
        logger.debug(f"过滤timeUnit中无用的识别词 {res}")
        return res