# -*- coding: utf-8 -*-
"""
任务服务 v9.0 - 业务逻辑聚合

职责：
1. 任务创建与持久化
2. 任务执行调度
3. 状态同步（DB + Event）
4. 用户隔离
"""

import asyncio
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from loguru import logger

from core.database import get_database, Database
from core.events import get_event_bus, EventBus, TaskEvent, EventType


@dataclass
class TaskConfig:
    """任务执行配置
    
    Attributes:
        enable_fetch: 启用题目拉取
        enable_generation: 启用数据生成
        enable_upload: 启用上传
        enable_solve: 启用求解
        source_adapter: 全局拉取适配器（旧格式）
        target_adapter: 上传目标适配器
        problem_adapters: 每题独立拉取适配器映射 {problem_id: adapter_name}
        llm_provider: 统一LLM提供商（生成+求解统一使用）
    """
    enable_fetch: bool = True
    enable_generation: bool = True
    enable_upload: bool = True
    enable_solve: bool = True
    source_adapter: Optional[str] = None
    target_adapter: Optional[str] = None
    problem_adapters: Optional[Dict[str, str]] = None
    llm_provider: Optional[str] = "deepseek"  # 统一LLM（生成+求解）
    
    def get_fetch_adapter(self, problem_id: str) -> Optional[str]:
        """获取指定题目的拉取适配器
        
        优先级: problem_adapters[problem_id] > source_adapter > None(自动)
        """
        from loguru import logger
        
        if self.problem_adapters and problem_id in self.problem_adapters:
            adapter = self.problem_adapters[problem_id]
            logger.info(f"[TaskConfig] 题目 {problem_id} 从 problem_adapters 获取适配器: {adapter}")
            return adapter if adapter != 'auto' else None
        
        logger.info(f"[TaskConfig] 题目 {problem_id} 使用 source_adapter: {self.source_adapter}")
        return self.source_adapter
    
    def to_modules_dict(self) -> Dict[str, bool]:
        """转换为 Pipeline 模块配置"""
        return {
            "fetch": self.enable_fetch,
            "gen": self.enable_generation,
            "upload": self.enable_upload,
            "solve": self.enable_solve,
            "training": False
        }


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: int
    problem_id: str
    success: bool
    status: str
    uploaded_url: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[str] = None
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []


class TaskService:
    """
    任务服务 - 业务逻辑聚合
    
    特性：
    1. 任务创建与持久化
    2. Pipeline 执行调度
    3. 状态同步（DB + EventBus）
    4. 用户隔离
    5. 重试机制
    """
    
    _instance: Optional['TaskService'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db: Database = None, event_bus: EventBus = None):
        if self._initialized:
            return
        
        self._db = db
        self._event_bus = event_bus
        self._broadcast_callback: Optional[Callable] = None
        
        # 专用线程池执行 Pipeline（避免阻塞事件循环）
        # 线程池大小从并发配置中读取
        from concurrent.futures import ThreadPoolExecutor
        from services.concurrency_manager import get_concurrency_manager
        concurrency_config = get_concurrency_manager().get_config()
        max_workers = concurrency_config.get("max_global_tasks", 50)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pipeline_")
        
        # 任务取消追踪
        self._cancelled_tasks: set = set()
        self._running_tasks: Dict[int, Any] = {}  # task_id -> future
        self._shutting_down = False
        
        self._initialized = True
        
        logger.info(f"[TaskService] 任务服务初始化完成（线程池: {max_workers} workers）")
    
    def shutdown(self, wait: bool = False):
        """关闭服务，取消所有运行中的任务
        
        Args:
            wait: 是否等待任务完成
        """
        logger.info("[TaskService] 正在关闭...")
        self._shutting_down = True
        
        # 标记所有任务为取消
        for task_id in list(self._running_tasks.keys()):
            self.cancel_task(task_id)
        
        # 关闭线程池
        if self._executor:
            try:
                # 先尝试优雅关闭
                self._executor.shutdown(wait=wait, cancel_futures=True)
            except Exception as e:
                logger.warning(f"[TaskService] 线程池关闭异常: {e}")
            finally:
                self._executor = None
            logger.info("[TaskService] 线程池已关闭")
    
    @property
    def is_shutting_down(self) -> bool:
        """检查是否正在关闭"""
        return self._shutting_down
    
    @property
    def db(self) -> Database:
        """获取数据库实例"""
        if self._db is None:
            self._db = get_database()
        return self._db
    
    @property
    def event_bus(self) -> EventBus:
        """获取事件总线"""
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus
    
    def set_broadcast_callback(self, callback: Callable):
        """设置 WebSocket 广播回调"""
        self._broadcast_callback = callback
    
    async def _broadcast(self, message: dict):
        """广播消息"""
        if self._broadcast_callback:
            try:
                await self._broadcast_callback(message)
            except Exception as e:
                logger.debug(f"广播失败: {e}")
    
    # ==================== 任务创建 ====================
    
    def create_task(
        self,
        user_id: int,
        problem_id: str,
        source_oj: Optional[str] = None,
        target_oj: Optional[str] = None
    ) -> int:
        """创建单个任务"""
        task_id = self.db.create_task(
            user_id=user_id,
            problem_id=problem_id,
            source_oj=source_oj,
            target_oj=target_oj
        )
        logger.info(f"创建任务: id={task_id}, user={user_id}, problem={problem_id}")
        return task_id
    
    def create_tasks(
        self,
        user_id: int,
        problem_ids: List[str],
        config: TaskConfig
    ) -> List[Dict]:
        """批量创建任务"""
        created_tasks = []
        
        for pid in problem_ids:
            try:
                task_id = self.create_task(
                    user_id=user_id,
                    problem_id=pid,
                    source_oj=config.source_adapter,
                    target_oj=config.target_adapter
                )
                created_tasks.append({"id": task_id, "problem_id": pid})
            except Exception as e:
                logger.error(f"创建任务失败 (problem_id={pid}): {e}")
        
        # 记录活动
        if created_tasks:
            self.db.log_activity(
                user_id, "create_task",
                str(created_tasks[0]["id"]),
                {"problem_ids": problem_ids, "count": len(created_tasks)}
            )
        
        return created_tasks
    
    # ==================== 任务执行 ====================
    
    async def execute_tasks(
        self,
        tasks: List[Dict],
        config: TaskConfig,
        user_id: int
    ):
        """执行任务列表（并行执行）"""
        # 创建并行任务
        async_tasks = []
        for task_info in tasks:
            task_id = task_info["id"]
            problem_id = task_info["problem_id"]
            
            # 检查是否被取消或正在关闭
            if self.is_task_cancelled(task_id) or self._shutting_down:
                logger.info(f"[TaskService] 任务 {task_id} 已取消或服务关闭中，跳过执行")
                self.clear_cancelled(task_id)
                continue
            
            # 创建异步任务
            async_tasks.append(
                self._execute_single_task(task_id, problem_id, config, user_id)
            )
        
        # 并行执行所有任务
        if async_tasks:
            logger.info(f"[TaskService] 开始并行执行 {len(async_tasks)} 个任务")
            try:
                await asyncio.gather(*async_tasks, return_exceptions=True)
            except asyncio.CancelledError:
                logger.info(f"[TaskService] 任务批次执行被取消")
            except Exception as e:
                logger.warning(f"[TaskService] 任务批次执行异常: {e}")
    
    async def _execute_single_task(
        self,
        task_id: int,
        problem_id: str,
        config: TaskConfig,
        user_id: int
    ):
        """执行单个任务"""
        try:
            # 检查是否已关闭
            if self._shutting_down:
                logger.info(f"[TaskService] 服务关闭中，跳过任务 {task_id}")
                return
            
            # 更新状态为运行中
            self.db.update_task(task_id, status=1, stage="running")
            
            # 广播开始事件
            await self._broadcast({
                "type": "task.started",
                "task_id": task_id,
                "problem_id": problem_id,
                "user_id": user_id
            })
            
            # 执行 Pipeline
            result = await self._execute_pipeline(
                problem_id=problem_id,
                config=config,
                user_id=user_id,
                task_id=task_id
            )
            
            # 处理结果
            if result.success:
                self.db.update_task(
                    task_id,
                    status=4,
                    stage="completed",
                    progress=100,
                    uploaded_url=result.uploaded_url
                )
                await self._broadcast({
                    "type": "task.completed",
                    "task_id": task_id,
                    "problem_id": problem_id,
                    "status": "success",
                    "uploaded_url": result.uploaded_url
                })
            else:
                self.db.update_task(
                    task_id,
                    status=-1,
                    stage="failed",
                    error_message=result.error_message
                )
                await self._broadcast({
                    "type": "task.failed",
                    "task_id": task_id,
                    "problem_id": problem_id,
                    "status": "failed",
                    "error": result.error_message
                })
                
        except asyncio.CancelledError:
            # 任务被取消（服务器关闭）
            logger.info(f"[TaskService] 任务 {task_id} ({problem_id}) 被取消")
            self.db.update_task(
                task_id,
                status=-1,
                stage="cancelled",
                error_message="任务被取消"
            )
            # 不要重新抛出，让 gather 继续处理其他任务
        except Exception as e:
            logger.exception(f"任务 {task_id} (problem={problem_id}) 执行失败")
            self.db.update_task(
                task_id,
                status=-1,
                stage="failed",
                error_message=str(e)
            )
            await self._broadcast({
                "type": "task.failed",
                "task_id": task_id,
                "problem_id": problem_id,
                "error": str(e)
            })
    
    async def _execute_pipeline(
        self,
        problem_id: str,
        config: TaskConfig,
        user_id: int,
        task_id: int
    ) -> TaskResult:
        """执行单个题目的 Pipeline"""
        from services.unified_config import get_config_manager
        from services.pipeline import PipelineRunner
        
        logger.info(f"[Pipeline] 任务 {task_id}: {problem_id}")
        
        # 获取配置管理器
        cfg_mgr = get_config_manager()
        # 注意：不再覆盖全局 cfg.adapter_configs
        # 适配器配置已改为从 context.user_id 动态读取用户配置
        
        # 设置统一LLM provider（生成+求解使用同一个）
        if config.llm_provider:
            cfg_mgr.cfg.llm_provider_generation = config.llm_provider
            cfg_mgr.cfg.llm_provider_solution = config.llm_provider
            logger.info(f"[Pipeline] 使用统一 LLM: {config.llm_provider}")
        
        # 获取此任务的专属拉取适配器（任务级别隔离，不修改共享配置）
        fetch_adapter = config.get_fetch_adapter(problem_id)
        logger.info(f"[Pipeline] 任务 {task_id} 拉取适配器: {fetch_adapter or 'auto'}")
        
        # 构建模块适配器设置（仅用于上传/提交适配器）
        module_settings = self.db.get_user_module_settings(user_id)
        
        # 确定上传适配器：请求指定 > 数据库设置 > 默认值 shsoj
        upload_adapter = config.target_adapter
        if not upload_adapter or not upload_adapter.strip():
            upload_adapter = module_settings.get('upload', {}).get('adapter')
        if not upload_adapter or not upload_adapter.strip():
            upload_adapter = 'shsoj'  # 最终默认值
        
        # 设置上传/提交适配器
        module_settings['upload'] = {'mode': 'manual', 'adapter': upload_adapter}
        module_settings['submit'] = {'mode': 'manual', 'adapter': upload_adapter}
        logger.info(f"[Pipeline] 上传适配器: {upload_adapter} (请求: '{config.target_adapter}')")
        
        cfg_mgr.cfg.module_adapter_settings = module_settings
        
        # 创建 Pipeline（传入任务专属的拉取适配器）
        pipeline = PipelineRunner(
            cfg_mgr, 
            user_id=user_id,
            fetch_adapter_override=fetch_adapter  # 任务级别隔离
        )
        pipeline._current_task_id = task_id
        
        # 传递取消检查函数给 Pipeline（包括服务关闭检查）
        pipeline._cancellation_check = lambda: self.is_task_cancelled(task_id) or self._shutting_down
        
        # 检查是否在执行前已取消或服务关闭
        if self.is_task_cancelled(task_id) or self._shutting_down:
            logger.info(f"[Pipeline] 任务 {task_id} 在执行前已取消或服务关闭")
            return TaskResult(task_id=task_id, problem_id=problem_id, success=False, status="cancelled", error_message="任务已取消")
        
        # 执行（使用专用线程池，避免阻塞事件循环）
        # force_process_finished=True: 用户主动提交的任务始终执行，不跳过已完成题目
        def run_pipeline():
            """在线程池中执行 pipeline，添加日志追踪"""
            logger.info(f"[Pipeline] 任务 {task_id} 线程开始执行 (problem={problem_id})")
            try:
                return pipeline.run([problem_id], config.to_modules_dict(), force_process_finished=True)
            finally:
                logger.info(f"[Pipeline] 任务 {task_id} 线程执行结束 (problem={problem_id})")
        
        try:
            # 检查线程池是否可用
            if self._executor is None or self._shutting_down:
                return TaskResult(task_id=task_id, problem_id=problem_id, success=False, status="cancelled", error_message="服务关闭中")
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, run_pipeline)
        except (asyncio.CancelledError, RuntimeError, TypeError) as e:
            # 服务关闭、线程池已关闭或事件循环取消
            if not self._shutting_down:
                logger.info(f"[Pipeline] 任务 {task_id} 执行被中断")
            return TaskResult(task_id=task_id, problem_id=problem_id, success=False, status="cancelled", error_message="任务被取消")
        
        # 检查执行后是否被取消
        if self.is_task_cancelled(task_id):
            logger.info(f"[Pipeline] 任务 {task_id} 执行期间被取消")
            self.clear_cancelled(task_id)
            return TaskResult(task_id=task_id, problem_id=problem_id, success=False, status="cancelled", error_message="任务已取消")
        
        # 收集日志
        logs = pipeline.per_logs.get(problem_id, [])
        
        # 读取工作区日志（使用正确的工作区路径）
        from services.problem_id import get_problem_id_resolver
        resolver = get_problem_id_resolver()
        workspace_dir = resolver.get_workspace_dir(problem_id, user_id)
        log_file = workspace_dir / "pipeline.log"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    logs.extend(f.read().strip().split("\n"))
            except Exception:
                pass
        
        # 从 Pipeline 结果提取结构化数据
        uploaded_url = None
        success = False
        error_message = None
        
        if result:
            results_list = result if isinstance(result, list) else [result]
            for task_result in results_list:
                # 使用结构化字段判断成功
                if hasattr(task_result, 'ok_gen') or hasattr(task_result, 'ok_upload') or hasattr(task_result, 'ok_solve'):
                    # 根据配置的模块判断成功
                    module_success = []
                    if config.enable_generation and hasattr(task_result, 'ok_gen'):
                        module_success.append(task_result.ok_gen)
                    if config.enable_upload and hasattr(task_result, 'ok_upload'):
                        module_success.append(task_result.ok_upload)
                    if config.enable_solve and hasattr(task_result, 'ok_solve'):
                        module_success.append(task_result.ok_solve)
                    
                    # 所有启用的模块都成功才算成功
                    success = all(module_success) if module_success else True
                
                # 提取上传 URL
                if hasattr(task_result, 'extra') and task_result.extra:
                    uploaded_url = task_result.extra.get('uploaded_url')
                    if task_result.extra.get('error'):
                        error_message = task_result.extra.get('error')
                        success = False
        
        # 如果没有结构化结果，回退到日志解析（兼容）
        if result is None or (not success and not error_message):
            has_error = any("✗" in log or "失败" in log for log in logs if isinstance(log, str))
            if has_error:
                success = False
                error_message = next((log for log in reversed(logs) if "✗" in log or "失败" in log), None)
        
        return TaskResult(
            task_id=task_id,
            problem_id=problem_id,
            success=success,
            status="success" if success else "failed",
            uploaded_url=uploaded_url,
            error_message=error_message,
            logs=logs
        )
    
    # ==================== 任务查询 ====================
    
    def get_user_tasks(
        self,
        user_id: int,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        source_oj: Optional[str] = None,
        target_oj: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取用户任务列表（带筛选）"""
        tasks = self.db.get_user_tasks(user_id, limit=limit)
        
        # 应用筛选
        filtered = []
        for task in tasks:
            # 搜索筛选
            if search and search.lower() not in (task.get("problem_id") or "").lower():
                continue
            
            # 状态筛选
            if status_filter:
                task_status = task.get("status", 0)
                if status_filter == "completed" and task_status != 4:
                    continue
                elif status_filter == "running" and task_status not in [1, 2]:
                    continue
                elif status_filter == "failed" and task_status != -1:
                    continue
                elif status_filter == "pending" and task_status != 0:
                    continue
            
            # OJ 筛选
            if source_oj:
                task_source = task.get("source_oj") or ""
                if task_source and task_source.lower() != source_oj.lower():
                    continue
            
            if target_oj:
                task_target = task.get("target_oj") or ""
                if task_target and task_target.lower() != target_oj.lower():
                    continue
            
            filtered.append(task)
        
        return filtered
    
    def get_task(self, task_id: int, user_id: int, is_admin: bool = False) -> Optional[Dict]:
        """获取任务详情"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        
        if not task:
            return None
        
        task = dict(task)
        
        # 权限检查
        if task.get("user_id") != user_id and not is_admin:
            return None
        
        return task
    
    def get_task_logs(self, task_id: int, user_id: int, is_admin: bool = False) -> List[str]:
        """获取任务日志"""
        from services.problem_id import get_problem_id_resolver
        
        task = self.get_task(task_id, user_id, is_admin)
        if not task:
            logger.debug(f"[get_task_logs] 未找到任务: task_id={task_id}, user_id={user_id}")
            return []
        
        problem_id = task.get("problem_id")
        task_user_id = task.get("user_id")
        logs = []
        
        logger.debug(f"[get_task_logs] task_id={task_id}, problem_id={problem_id}, task_user_id={task_user_id}")
        
        if problem_id and task_user_id:
            # 使用 ProblemIdResolver 获取正确的工作区路径
            resolver = get_problem_id_resolver()
            workspace_dir = resolver.get_workspace_dir(problem_id, task_user_id)
            log_file = workspace_dir / "pipeline.log"
            
            logger.debug(f"[get_task_logs] 尝试读取日志: {log_file}, exists={log_file.exists()}")
            
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        logs = [line.strip() for line in f.readlines() if line.strip()]
                    logger.debug(f"[get_task_logs] 读取到 {len(logs)} 行日志")
                except Exception as e:
                    logger.warning(f"读取日志失败: {e}")
            else:
                # 日志文件不存在时，尝试查找可能的备选路径
                logger.debug(f"[get_task_logs] 日志文件不存在: {log_file}")
                # 检查父目录是否存在
                if workspace_dir.exists():
                    logger.debug(f"[get_task_logs] 工作目录存在，列出内容: {list(workspace_dir.iterdir())[:5]}")
        
        if not logs:
            logs = ["暂无日志记录", f"task_id: {task_id}", f"problem_id: {problem_id or 'N/A'}", f"工作目录: {workspace_dir if problem_id and task_user_id else 'N/A'}"]
        
        return logs
    
    # ==================== 任务操作 ====================
    
    def cancel_task(self, task_id: int) -> bool:
        """取消正在运行的任务"""
        self._cancelled_tasks.add(task_id)
        
        # 尝试取消 future
        if task_id in self._running_tasks:
            future = self._running_tasks.pop(task_id, None)
            if future and not future.done():
                future.cancel()
                logger.info(f"[TaskService] 任务 {task_id} 已标记取消")
                return True
        
        logger.info(f"[TaskService] 任务 {task_id} 已标记取消（可能已完成）")
        return True
    
    def is_task_cancelled(self, task_id: int) -> bool:
        """检查任务是否被取消"""
        return task_id in self._cancelled_tasks
    
    def clear_cancelled(self, task_id: int):
        """清除取消标记"""
        self._cancelled_tasks.discard(task_id)
        self._running_tasks.pop(task_id, None)
    
    def delete_task(self, task_id: int, user_id: int, is_admin: bool = False) -> bool:
        """删除任务（仅删除数据库记录）
        
        规则：
        - 立即删除数据库中的任务记录（保证数据一致性）
        - 取消正在运行的任务
        - 本地数据删除应在后台执行（通过 delete_task_data 方法）
        
        Returns:
            bool: 删除是否成功
        """
        task = self.get_task(task_id, user_id, is_admin)
        if not task:
            return False
        
        # 先取消运行中的任务
        self.cancel_task(task_id)
        
        problem_id = task.get("problem_id")
        
        # 删除数据库记录（立即执行，保证一致性）
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.db.conn.commit()
        
        # 记录活动
        self.db.log_activity(
            user_id, "delete_task",
            str(task_id),
            {"problem_id": problem_id}
        )
        
        logger.info(f"[TaskService] 任务 {task_id} 已从数据库删除")
        return True
    
    def delete_task_data(self, task_id: int, problem_id: str, user_id: int) -> None:
        """删除任务的本地数据（后台执行）
        
        规则：
        - 如果题目已 AC（ok_solve=True），保留本地数据（可复用）
        - 如果题目未 AC，删除本地数据
        
        注意：此方法应在后台任务中调用，不会阻塞主流程
        
        Args:
            task_id: 任务ID（用于日志）
            problem_id: 题目ID
            user_id: 用户ID
        """
        if not problem_id:
            return
        
        try:
            from services.problem_data_manager import ProblemDataManager
            from services.problem_id import get_problem_id_resolver
            
            resolver = get_problem_id_resolver()
            workspace_dir = resolver.get_workspace_dir(problem_id, user_id)
            
            if not workspace_dir.exists():
                logger.debug(f"[TaskService] 任务 {task_id} ({problem_id}) 本地数据目录不存在，跳过删除")
                return
            
            is_ac = ProblemDataManager.is_completed(workspace_dir)
            
            if is_ac:
                # 已 AC，保留本地数据（可供复用）
                logger.info(f"[TaskService] 任务 {task_id} ({problem_id}) 已AC，保留本地数据: {workspace_dir}")
            else:
                # 未 AC，删除本地数据
                import shutil
                try:
                    logger.info(f"[TaskService] 开始删除任务 {task_id} ({problem_id}) 的本地数据: {workspace_dir}")
                    shutil.rmtree(workspace_dir)
                    logger.info(f"[TaskService] ✓ 任务 {task_id} ({problem_id}) 本地数据已删除")
                except Exception as e:
                    logger.error(f"[TaskService] ✗ 删除任务 {task_id} ({problem_id}) 本地数据失败: {e}")
        except Exception as e:
            logger.error(f"[TaskService] 删除任务 {task_id} 本地数据时发生异常: {e}")
    
    async def retry_task(
        self,
        task_id: int,
        user_id: int,
        module: str = "all",
        is_admin: bool = False
    ) -> Optional[int]:
        """重试任务（原地重试，不创建新任务）
        
        注意：
        1. 管理员重试其他用户的任务时，使用原用户的配置
        2. 重试会更新原任务状态，不会创建新任务
        3. 正在运行的任务不能重试
        4. 同一任务不能并发重试
        """
        task = self.get_task(task_id, user_id, is_admin)
        if not task:
            return None
        
        # 检查任务状态：运行中的任务不能重试
        current_status = task.get("status")
        if current_status == 1:  # running
            logger.warning(f"[retry_task] 任务 {task_id} 正在运行中，不能重试")
            return None
        
        # 并发保护：检查是否正在被重试
        if task_id in self._running_tasks:
            logger.warning(f"[retry_task] 任务 {task_id} 已在重试队列中，不能重复重试")
            return None
        
        problem_id = task.get("problem_id")
        if not problem_id:
            return None
        
        # 获取原任务所有者的 user_id（管理员重试时使用原用户配置）
        original_user_id = task.get("user_id")
        if not original_user_id:
            original_user_id = user_id  # 兜底：使用当前用户
        
        # 构建重试配置
        config = TaskConfig(
            enable_fetch=(module == "fetch" or module == "all"),
            enable_generation=(module == "gen" or module == "all"),
            enable_upload=(module == "upload" or module == "all"),
            enable_solve=(module == "solve" or module == "all"),
            source_adapter=task.get("source_oj"),
            target_adapter=task.get("target_oj")
        )
        
        # 重置原任务状态（不创建新任务）
        self.db.update_task(
            task_id, 
            status=0,  # pending
            stage="retry_pending",
            progress=0,
            error_message=None
        )
        
        # 记录活动（记录操作者是谁，管理员代理重试时记录两个user_id）
        self.db.log_activity(
            user_id, "retry_task",
            str(task_id),
            {
                "module": module, 
                "original_user_id": original_user_id, 
                "retry_in_place": True,
                "is_admin_proxy": user_id != original_user_id
            }
        )
        
        logger.info(f"[retry_task] 开始重试任务 {task_id} (用户={original_user_id}, 操作者={user_id}, 模块={module})")
        
        # 异步执行重试（使用原用户配置）
        import asyncio
        asyncio.create_task(self._execute_single_retry(task_id, config, original_user_id, problem_id))
        
        # 返回原任务ID（不是新任务）
        return task_id
    
    async def _execute_single_retry(
        self,
        task_id: int,
        config: TaskConfig,
        user_id: int,
        problem_id: str
    ):
        """执行单个重试任务"""
        # 标记任务正在运行（防止并发重试）
        self._running_tasks[task_id] = True
        
        try:
            self.db.update_task(task_id, status=1, stage="running")
            
            result = await self._execute_pipeline(
                problem_id=problem_id,
                config=config,
                user_id=user_id,
                task_id=task_id
            )
            
            if result.success:
                self.db.update_task(
                    task_id, status=4, stage="completed",
                    progress=100, uploaded_url=result.uploaded_url
                )
                logger.info(f"[_execute_single_retry] 任务 {task_id} 重试成功")
            else:
                self.db.update_task(
                    task_id, status=-1, stage="failed",
                    error_message=result.error_message
                )
                logger.warning(f"[_execute_single_retry] 任务 {task_id} 重试失败: {result.error_message}")
        except Exception as e:
            logger.exception(f"[_execute_single_retry] 任务 {task_id} 执行异常")
            self.db.update_task(task_id, status=-1, stage="failed", error_message=str(e))
        finally:
            # 清理运行状态（无论成功失败都要清理）
            self._running_tasks.pop(task_id, None)
    
    # ==================== 统计 ====================
    
    def get_user_stats(self, user_id: int) -> Dict:
        """获取用户任务统计"""
        tasks = self.db.get_user_tasks(user_id, limit=10000)
        
        return {
            "total": len(tasks),
            "success": sum(1 for t in tasks if t.get("status") == 4),
            "running": sum(1 for t in tasks if t.get("status") == 1),
            "failed": sum(1 for t in tasks if t.get("status") == -1),
            "pending": sum(1 for t in tasks if t.get("status") == 0)
        }
    
    def get_global_stats(self) -> Dict:
        """获取全局任务统计（管理员）"""
        tasks = self.db.get_all_tasks(limit=10000)
        users = self.db.get_all_users()
        
        return {
            "tasks": {
                "total": len(tasks),
                "success": sum(1 for t in tasks if t.get("status") == 4),
                "running": sum(1 for t in tasks if t.get("status") == 1),
                "failed": sum(1 for t in tasks if t.get("status") == -1),
                "pending": sum(1 for t in tasks if t.get("status") == 0)
            },
            "users": {
                "total": len(users),
                "active": sum(1 for u in users if u.get("status") == "active"),
                "inactive": sum(1 for u in users if u.get("status") != "active")
            }
        }


# ==================== 全局访问函数 ====================

_task_service: Optional[TaskService] = None


def get_task_service() -> TaskService:
    """获取任务服务实例"""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service
