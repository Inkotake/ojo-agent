"""
提交处理策略
消除硬编码的if-else状态判断
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from loguru import logger


class SubmissionStatus(str, Enum):
    """提交状态"""
    PENDING = "Pending"
    JUDGING = "Judging"
    ACCEPTED = "Accepted"
    COMPILE_ERROR = "Compile Error"
    WRONG_ANSWER = "Wrong Answer"
    TIME_LIMIT = "Time Limit Exceeded"
    MEMORY_LIMIT = "Memory Limit Exceeded"
    RUNTIME_ERROR = "Runtime Error"
    SYSTEM_ERROR = "System Error"


@dataclass
class SubmissionContext:
    """提交上下文"""
    problem_id: str
    code: str
    status: SubmissionStatus
    retry_count: int = 0
    max_retries: int = 5
    error_message: str = ""
    failed_cases: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_to_history(self, data: Dict[str, Any]) -> None:
        """添加到历史记录"""
        self.history.append(data)
    
    def can_retry(self) -> bool:
        """是否可以重试"""
        return self.retry_count < self.max_retries


class SubmissionStrategy(ABC):
    """提交处理策略基类"""
    
    @abstractmethod
    def can_handle(self, status: SubmissionStatus) -> bool:
        """检查是否能处理指定状态"""
        pass
    
    @abstractmethod
    async def handle(self, context: SubmissionContext) -> SubmissionContext:
        """处理提交"""
        pass
    
    def get_name(self) -> str:
        """获取策略名称"""
        return self.__class__.__name__


class AcceptedStrategy(SubmissionStrategy):
    """AC策略 - 成功完成"""
    
    def can_handle(self, status: SubmissionStatus) -> bool:
        return status == SubmissionStatus.ACCEPTED
    
    async def handle(self, context: SubmissionContext) -> SubmissionContext:
        logger.info(f"[{context.problem_id}] AC成功！")
        return context


class CompileErrorStrategy(SubmissionStrategy):
    """CE策略 - 编译错误重试"""
    
    MAX_RETRIES = 3
    COOLDOWN_SECONDS = 30
    
    def can_handle(self, status: SubmissionStatus) -> bool:
        return status == SubmissionStatus.COMPILE_ERROR
    
    async def handle(self, context: SubmissionContext) -> SubmissionContext:
        if context.retry_count >= self.MAX_RETRIES:
            logger.error(f"[{context.problem_id}] CE重试次数已达上限")
            return context
        
        logger.warning(f"[{context.problem_id}] 编译错误，等待{self.COOLDOWN_SECONDS}秒后重试...")
        await asyncio.sleep(self.COOLDOWN_SECONDS)
        
        # 降低温度重新生成
        context.add_to_history({
            "attempt": context.retry_count + 1,
            "result": "CE",
            "message": context.error_message
        })
        context.retry_count += 1
        
        # 标记需要重新生成代码（由外部处理）
        logger.info(f"[{context.problem_id}] CE重试 {context.retry_count}/{self.MAX_RETRIES}")
        
        return context


class WrongAnswerStrategy(SubmissionStrategy):
    """WA策略 - 答案错误增量修复"""
    
    MAX_RETRIES = 5
    INCREMENTAL_RETRY_START = 2
    INCREMENTAL_RETRY_END = 3
    
    def can_handle(self, status: SubmissionStatus) -> bool:
        return status == SubmissionStatus.WRONG_ANSWER
    
    async def handle(self, context: SubmissionContext) -> SubmissionContext:
        if context.retry_count >= self.MAX_RETRIES:
            logger.error(f"[{context.problem_id}] WA重试次数已达上限")
            return context
        
        # 判断使用增量修复还是完全重新生成
        use_incremental = (
            self.INCREMENTAL_RETRY_START <= context.retry_count + 1 <= self.INCREMENTAL_RETRY_END
        )
        
        context.add_to_history({
            "attempt": context.retry_count + 1,
            "result": "WA",
            "failed_cases": context.failed_cases,
            "message": context.error_message,
            "use_incremental": use_incremental
        })
        context.retry_count += 1
        
        if use_incremental:
            logger.info(f"[{context.problem_id}] WA增量修复 {context.retry_count}/{self.MAX_RETRIES}")
        else:
            logger.info(f"[{context.problem_id}] WA完全重新生成 {context.retry_count}/{self.MAX_RETRIES}")
        
        return context


class TimeLimitStrategy(SubmissionStrategy):
    """TLE策略 - 超时优化"""
    
    MAX_RETRIES = 3
    
    def can_handle(self, status: SubmissionStatus) -> bool:
        return status == SubmissionStatus.TIME_LIMIT
    
    async def handle(self, context: SubmissionContext) -> SubmissionContext:
        if context.retry_count >= self.MAX_RETRIES:
            logger.error(f"[{context.problem_id}] TLE重试次数已达上限")
            return context
        
        context.add_to_history({
            "attempt": context.retry_count + 1,
            "result": "TLE",
            "message": "需要优化算法"
        })
        context.retry_count += 1
        
        logger.info(f"[{context.problem_id}] TLE，重新生成更高效算法 {context.retry_count}/{self.MAX_RETRIES}")
        
        return context


class RuntimeErrorStrategy(SubmissionStrategy):
    """RE策略 - 运行时错误修复"""
    
    MAX_RETRIES = 3
    
    def can_handle(self, status: SubmissionStatus) -> bool:
        return status == SubmissionStatus.RUNTIME_ERROR
    
    async def handle(self, context: SubmissionContext) -> SubmissionContext:
        if context.retry_count >= self.MAX_RETRIES:
            logger.error(f"[{context.problem_id}] RE重试次数已达上限")
            return context
        
        context.add_to_history({
            "attempt": context.retry_count + 1,
            "result": "RE",
            "message": context.error_message
        })
        context.retry_count += 1
        
        logger.info(f"[{context.problem_id}] RE，修复运行错误 {context.retry_count}/{self.MAX_RETRIES}")
        
        return context


class SubmissionStrategyManager:
    """提交策略管理器"""
    
    def __init__(self):
        self._strategies: List[SubmissionStrategy] = []
        
        # 注册默认策略
        self.register_strategy(AcceptedStrategy())
        self.register_strategy(CompileErrorStrategy())
        self.register_strategy(WrongAnswerStrategy())
        self.register_strategy(TimeLimitStrategy())
        self.register_strategy(RuntimeErrorStrategy())
    
    def register_strategy(self, strategy: SubmissionStrategy) -> None:
        """注册策略"""
        self._strategies.append(strategy)
        logger.debug(f"注册提交策略: {strategy.get_name()}")
    
    async def handle_submission(self, context: SubmissionContext) -> SubmissionContext:
        """处理提交"""
        for strategy in self._strategies:
            if strategy.can_handle(context.status):
                return await strategy.handle(context)
        
        # 默认策略：不处理
        logger.warning(f"[{context.problem_id}] 未找到匹配的处理策略: {context.status}")
        return context
    
    def get_strategy(self, status: SubmissionStatus) -> Optional[SubmissionStrategy]:
        """获取处理指定状态的策略"""
        for strategy in self._strategies:
            if strategy.can_handle(status):
                return strategy
        return None

