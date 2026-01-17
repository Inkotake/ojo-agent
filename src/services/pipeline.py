# -*- coding: utf-8 -*-
"""
Pipeline v8.0 - 架构重构版

基于现有项目架构的完整重构：
- 使用 ProblemDataManager 跟踪处理状态（替代 finished.txt）
- 使用 ProblemIdResolver 统一 ID 处理
- 使用数据库 tasks 表管理任务
- 服务实例复用（避免每次任务创建新实例）
- 事件驱动的状态通知
- 智能重试策略（CE降温、WA/PAC上下文传递）
"""
from __future__ import annotations

import time
import json
import random
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

from loguru import logger

# 核心模块
from core.events import get_event_bus, EventBus, TaskEvent, EventType
from utils.concurrency import interruptible_sleep
# ConfigCenter 已弃用，使用 unified_config.ConfigService
from core.database import get_database

# 服务模块
from services.unified_config import ConfigManager
from services.oj.registry import get_global_registry, AdapterRegistry
from services.oj.base.capabilities import OJCapability
from services.llm.factory import LLMFactory
from services.generator import GeneratorService
from services.uploader import UploadService
from services.solver import SolveService
from services.training_service import TrainingService
from services.solution_searcher import SolutionSearcher
from services.logger import configure_logger
from services.image_service import ImageService
from services.validation_service import ValidationService, ValidationConfig
from services.problem_data_manager import ProblemDataManager
from services.problem_id import get_problem_id_resolver, ProblemIdResolver
from services.user_context import get_user_context, UserContext

# 工具模块
from utils.concurrency import SemaphorePool, CancelToken
from utils.text import sanitize_filename


@dataclass
class TaskResult:
    """任务执行结果"""
    original_id: str
    ok_gen: bool = False
    ok_upload: bool = False
    ok_solve: bool = False
    ok_training: bool = False
    elapsed: float = 0.0
    extra: dict = field(default_factory=dict)


class ServiceContainer:
    """服务容器 - 管理服务实例的生命周期
    
    避免每个任务创建新的服务实例，提高性能
    """
    
    def __init__(self, cfg: Any, sems: SemaphorePool, workspace: Path, 
                 log_callback: Callable[[str], None]):
        self.cfg = cfg
        self.sems = sems
        self.workspace = workspace
        self.log_callback = log_callback
        
        # LLM 客户端（懒加载）
        self._llm_factory: Optional[LLMFactory] = None
        self._llm_gen = None
        self._llm_solve = None
        self._llm_ocr = None
        self._llm_summary = None
        
        # 服务实例
        self._image_service = None
        self._validation_service = None
        self._solution_searcher = None
    
    @property
    def llm_factory(self) -> LLMFactory:
        if self._llm_factory is None:
            self._llm_factory = LLMFactory(self.cfg)
        return self._llm_factory
    
    @property
    def llm_gen(self):
        if self._llm_gen is None:
            self._llm_gen = self.llm_factory.create_for_task("generation")
        return self._llm_gen
    
    @property
    def llm_solve(self):
        if self._llm_solve is None:
            self._llm_solve = self.llm_factory.create_for_task("solution")
        return self._llm_solve
    
    @property
    def llm_ocr(self):
        """OCR 客户端（懒加载，未配置时返回 None）"""
        if self._llm_ocr is None:
            try:
                self._llm_ocr = self.llm_factory.create_for_task("ocr")
            except ValueError as e:
                # OCR 未配置，记录警告但不阻塞
                logger.warning(f"OCR 客户端未配置: {e}，图片识别功能将不可用")
                return None
        return self._llm_ocr
    
    @property
    def llm_summary(self):
        if self._llm_summary is None and getattr(self.cfg, "enable_search_summary", True):
            try:
                self._llm_summary = self.llm_factory.create_for_task("summary")
            except Exception as e:
                logger.warning(f"创建总结LLM失败: {e}")
        return self._llm_summary
    
    @property
    def image_service(self) -> ImageService:
        """图片处理服务（OCR 可选，未配置时图片识别不可用）"""
        if self._image_service is None:
            self._image_service = ImageService(
                ocr_client=self.llm_ocr,  # 可能为 None
                max_workers=4,
                download_timeout=30
            )
        return self._image_service
    
    @property
    def validation_service(self) -> ValidationService:
        if self._validation_service is None:
            self._validation_service = ValidationService(config=ValidationConfig())
        return self._validation_service
    
    @property
    def solution_searcher(self) -> SolutionSearcher:
        if self._solution_searcher is None:
            self._solution_searcher = SolutionSearcher(
                None, self.workspace,
                enable_search=self.cfg.enable_solution_search,
                log_callback=self.log_callback
            )
        return self._solution_searcher
    
    def create_generator(self) -> GeneratorService:
        """创建生成器服务（每个任务可能需要独立实例）
        
        NOTE: OCR 客户端是可选的，如果未配置硅基流动 API Key，
        OCR 功能不可用，但不会阻塞数据生成流程。
        """
        return GeneratorService(
            None, self.llm_gen, self.llm_ocr,  # llm_ocr 可能为 None
            self.workspace, self.sems,
            log_callback=self.log_callback,
            code_exec_timeout_sec=self.cfg.code_exec_timeout_minutes * 60,
            solution_searcher=self.solution_searcher,
            summary_llm=self.llm_summary,
            solve_llm_client=self.llm_solve
        )


class PipelineRunner:
    """
    Pipeline 执行器 v8.0
    
    基于现有架构的完整重构版本
    """
    
    def __init__(self, cfg_mgr: ConfigManager, 
                 table_cb: Optional[Callable] = None, 
                 log_cb: Optional[Callable] = None,
                 user_id: Optional[int] = None,
                 fetch_adapter_override: Optional[str] = None):
        """初始化 Pipeline 执行器
        
        Args:
            cfg_mgr: 配置管理器
            table_cb: 表格回调
            log_cb: 日志回调
            user_id: 用户ID
            fetch_adapter_override: 拉取适配器覆盖（优先于全局配置）
        """
        self.cfg_mgr = cfg_mgr
        self.table_cb = table_cb or (lambda *a, **k: None)
        self.log_cb = log_cb or (lambda *a, **k: None)
        self.cancel = CancelToken()
        self.gui_signals = None
        self.per_logs: Dict[str, List[str]] = {}
        self.user_id = user_id
        
        # 拉取适配器覆盖（任务级别，优先于全局配置）
        self._fetch_adapter_override = fetch_adapter_override
        
        # 外部取消检查回调（由 TaskService 设置）
        self._cancellation_check: Optional[Callable[[], bool]] = None
        
        # 任务执行状态跟踪（用于事件推送）
        self._current_task_id: Optional[str] = None
        self._current_stage: Optional[str] = None
        self._current_progress: int = 0
        
        # 日志批量处理（避免高频日志阻塞前端，同时保证用户体验）
        self._log_batch_buffer: Dict[str, List[str]] = {}  # pid -> [log_lines]
        self._log_batch_last_flush: Dict[str, float] = {}  # pid -> last_flush_time
        self._log_batch_interval = 0.2  # 批量发送间隔（秒）
        self._log_batch_max_size = 20  # 达到此数量立即发送
        
        # 文件写入缓冲区（减少 I/O）
        self._file_write_buffer: Dict[str, List[str]] = {}  # pid -> [log_lines]
        self._file_write_last_flush: Dict[str, float] = {}  # pid -> last_flush_time
        self._file_write_interval = 1.0  # 文件写入间隔（秒）
        
        # 关键日志模式（这些日志立即发送，不限流）
        self._critical_log_patterns = [
            "========== ",  # 阶段分隔符
            "✓ ",  # 成功
            "✗ ",  # 失败
            "[UPLOAD]",  # 上传相关
            "[SOLVE]",  # 求解相关
            "[GEN]",  # 生成阶段
            "已达最大",  # 重试上限
            "任务完成",
            "任务已取消",
            "执行失败",
        ]
        
        # 配置日志
        configure_logger(cfg_mgr.cfg.log_level)
        
        # 核心组件
        self.event_bus: EventBus = get_event_bus()
        self.registry: AdapterRegistry = get_global_registry()
        self.id_resolver: ProblemIdResolver = get_problem_id_resolver()
        
        # 信号量池
        self.sems = SemaphorePool(
            cfg_mgr.cfg.llm_max_concurrency,
            cfg_mgr.cfg.oj_max_concurrency
        )
        
        # 初始化适配器
        self._initialize_adapters()
        
        # 用户上下文（用于认证缓存和用户隔离）
        self._user_context: Optional[UserContext] = None
        if self.user_id:
            # 从数据库获取用户名
            try:
                db = get_database()
                user = db.get_user_by_id(self.user_id)
                username = user.get("username") if user else f"user_{self.user_id}"
            except:
                username = f"user_{self.user_id}"
            self._user_context = get_user_context(self.user_id, username)
            self._user_context.increment_task()
        
        # 服务容器
        self._service_container: Optional[ServiceContainer] = None
        
        logger.info(f"Pipeline v8.0 初始化完成 (user_id={self.user_id})")
    
    def _initialize_adapters(self):
        """初始化所有适配器（传递 user_id 用于用户配置隔离）"""
        for name in ['shsoj', 'hydrooj', 'codeforces', 'luogu', 'atcoder', 'aicoders', 'manual']:
            try:
                adapter = self.registry.get_adapter(name)
                if adapter and hasattr(adapter, 'initialize'):
                    # 传递 user_id 到适配器 context，用于读取用户配置
                    adapter.initialize({
                        'config_manager': self.cfg_mgr,
                        'user_id': self.user_id  # 用户配置隔离
                    })
            except Exception as e:
                logger.debug(f"适配器初始化跳过 {name}: {e}")
    
    @property
    def services(self) -> ServiceContainer:
        """获取服务容器（懒加载）"""
        if self._service_container is None:
            self._service_container = ServiceContainer(
                cfg=self.cfg_mgr.cfg,
                sems=self.sems,
                workspace=self._get_workspace_base(),
                log_callback=self._append_log
            )
        return self._service_container
    
    # ==================== 工作区路径 ====================
    
    def _get_workspace_base(self) -> Path:
        """获取工作区基础目录（支持环境变量）"""
        import os
        # 优先使用环境变量，其次使用 /app/workspace（Docker），最后使用当前目录
        workspace_base = os.getenv("OJO_WORKSPACE")
        if not workspace_base:
            docker_workspace = Path("/app/workspace")
            if docker_workspace.exists():
                workspace_base = str(docker_workspace)
            else:
                workspace_base = "workspace"
        
        base_path = Path(workspace_base)
        if self.user_id:
            return base_path / f"user_{self.user_id}"
        return base_path
    
    def _problem_dir_for(self, pid: str) -> Path:
        """获取题目工作目录（带缓存）"""
        if not hasattr(self, '_canonical_cache'):
            self._canonical_cache = {}
        
        if pid not in self._canonical_cache:
            self._canonical_cache[pid] = self.id_resolver.canonicalize(pid)
        
        canonical = self._canonical_cache[pid]
        return self._get_workspace_base() / f"problem_{sanitize_filename(canonical)}"
    
    def _zip_path_for(self, pid: str) -> Path:
        """获取测试数据ZIP路径"""
        pdir = self._problem_dir_for(pid)
        safe_url = sanitize_filename(pid)
        return pdir / f"problem_{safe_url}_testcase.zip"
    
    # ==================== 状态管理 ====================
    
    def _is_completed(self, pid: str) -> bool:
        """检查题目是否已完成（使用 ProblemDataManager）"""
        pdir = self._problem_dir_for(pid)
        return ProblemDataManager.is_completed(pdir)
    
    def _mark_completed(self, pid: str, result: TaskResult):
        """标记题目为已完成"""
        pdir = self._problem_dir_for(pid)
        ProblemDataManager.set_processing_status(pdir, {
            "stage": "completed",
            "ok_gen": result.ok_gen,
            "ok_upload": result.ok_upload,
            "ok_solve": result.ok_solve,
            "elapsed": result.elapsed,
            "completed_at": datetime.now().isoformat()
        })
    
    def _update_stage(self, pid: str, stage: str, **kwargs):
        """更新处理阶段"""
        pdir = self._problem_dir_for(pid)
        status = {"stage": stage}
        status.update(kwargs)
        ProblemDataManager.set_processing_status(pdir, status)
        
        # 更新当前阶段（用于事件推送）
        self._current_stage = stage
        
        # 同步更新数据库中的任务阶段
        if self._current_task_id:
            try:
                db = get_database()
                db.update_task(self._current_task_id, stage=stage)
            except Exception as e:
                logger.debug(f"更新任务阶段到数据库失败: {e}")
    
    # ==================== 日志系统 ====================
    
    def _append_log(self, msg: str):
        """统一日志处理（智能批量处理，保证用户体验）
        
        策略：
        1. 关键日志（阶段变化、错误、成功）立即发送
        2. 普通日志（思考、代码片段）批量聚合后发送
        3. 文件写入使用缓冲区减少 I/O
        """
        import time
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {msg}"
        
        # 提取 pid
        pid = None
        if msg.startswith("[") and "]" in msg:
            pid = msg.split("]")[0][1:]
            self.per_logs.setdefault(pid, []).append(log_line)
            
            # 缓冲文件写入（减少 I/O）
            self._buffer_file_write(pid, log_line)
        
        # 写入 loguru（不限制频率，但降低日志级别避免控制台刷屏）
        if any(p in msg for p in ["[思考]", "[代码]"]):
            logger.debug(msg)  # 流式日志降级为 debug
        else:
            logger.info(msg)
        
        # 发布事件（智能批量处理）
        if pid:
            self._buffer_log_event(pid, msg, log_line)
    
    def _is_critical_log(self, msg: str) -> bool:
        """判断是否为关键日志（需要立即发送）"""
        return any(pattern in msg for pattern in self._critical_log_patterns)
    
    def _buffer_file_write(self, pid: str, log_line: str):
        """缓冲文件写入（减少 I/O 操作）"""
        import time
        
        # 确保日志文件路径已缓存
        if not hasattr(self, '_log_file_cache'):
            self._log_file_cache = {}
        
        if pid not in self._log_file_cache:
            pdir = self._problem_dir_for(pid)
            pdir.mkdir(parents=True, exist_ok=True)
            self._log_file_cache[pid] = pdir / "pipeline.log"
        
        # 添加到缓冲区
        if pid not in self._file_write_buffer:
            self._file_write_buffer[pid] = []
            self._file_write_last_flush[pid] = time.time()
        
        self._file_write_buffer[pid].append(log_line)
        
        # 检查是否需要刷新文件
        current_time = time.time()
        elapsed = current_time - self._file_write_last_flush.get(pid, 0)
        buffer_size = len(self._file_write_buffer[pid])
        
        # 达到时间间隔或缓冲区满时写入文件
        if elapsed >= self._file_write_interval or buffer_size >= 50:
            self._flush_file_buffer(pid)
    
    def _flush_file_buffer(self, pid: str):
        """刷新文件写入缓冲区"""
        import time
        
        if pid not in self._file_write_buffer or not self._file_write_buffer[pid]:
            return
        
        try:
            log_file = self._log_file_cache.get(pid)
            if log_file:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write("\n".join(self._file_write_buffer[pid]) + "\n")
        except Exception:
            pass
        
        self._file_write_buffer[pid] = []
        self._file_write_last_flush[pid] = time.time()
    
    def _buffer_log_event(self, pid: str, msg: str, log_line: str):
        """缓冲日志事件（智能批量发送）"""
        import time
        from datetime import datetime
        
        current_time = time.time()
        is_critical = self._is_critical_log(msg)
        
        # 初始化缓冲区
        if pid not in self._log_batch_buffer:
            self._log_batch_buffer[pid] = []
            self._log_batch_last_flush[pid] = current_time
        
        # 添加到缓冲区
        self._log_batch_buffer[pid].append(log_line)
        
        # 检查是否需要发送
        elapsed = current_time - self._log_batch_last_flush.get(pid, 0)
        buffer_size = len(self._log_batch_buffer[pid])
        
        should_flush = (
            is_critical or  # 关键日志立即发送
            elapsed >= self._log_batch_interval or  # 达到时间间隔
            buffer_size >= self._log_batch_max_size  # 缓冲区满
        )
        
        if should_flush:
            self._flush_log_events(pid)
    
    def _flush_log_events(self, pid: str):
        """刷新日志事件缓冲区（批量发送到前端）"""
        import time
        from datetime import datetime
        
        if pid not in self._log_batch_buffer or not self._log_batch_buffer[pid]:
            return
        
        try:
            logs = self._log_batch_buffer[pid]
            
            # 发送批量日志事件
            self.event_bus.publish_sync(TaskEvent(
                type=EventType.TASK_PROGRESS,
                task_id=self._current_task_id or "",
                problem_id=pid,
                stage=self._current_stage or "processing",
                progress=self._current_progress or 0,
                message=logs[-1] if logs else "",  # 最后一条日志作为主消息
                data={
                    "task_id": self._current_task_id or "",
                    "problem_id": pid,
                    "stage": self._current_stage or "processing",
                    "progress": self._current_progress or 0,
                    "logs": logs,  # 批量日志
                    "log_count": len(logs),
                    "timestamp": datetime.now().isoformat()
                }
            ))
        except Exception as e:
            logger.debug(f"刷新日志事件失败: {e}")
        
        # 清空缓冲区
        self._log_batch_buffer[pid] = []
        self._log_batch_last_flush[pid] = time.time()
        
        # 同时刷新文件缓冲区
        self._flush_file_buffer(pid)
    
    def _emit_status(self, row: int, status: Dict[str, str], elapsed: Optional[float] = None):
        """更新UI状态"""
        try:
            self.table_cb(row, status, elapsed)
            if self.gui_signals:
                self.gui_signals.taskUpdate.emit(row, {"status": status, "elapsed": elapsed or -1})
        except Exception:
            pass
    
    # ==================== 适配器获取 ====================
    
    def _get_fetch_adapter(self, pid: str):
        """获取题面拉取适配器（带缓存）
        
        优先级：
        1. _fetch_adapter_override（任务级别覆盖）
        2. module_adapter_settings 配置
        3. 自动检测
        """
        # 缓存适配器查找结果
        if not hasattr(self, '_adapter_cache'):
            self._adapter_cache = {}
        
        if pid in self._adapter_cache:
            return self._adapter_cache[pid]
        
        adapter = None
        
        # 1. 优先使用任务级别覆盖
        if self._fetch_adapter_override:
            adapter = self.registry.get_adapter(self._fetch_adapter_override)
            if adapter:
                logger.debug(f"[Pipeline] 使用任务覆盖适配器: {self._fetch_adapter_override}")
        
        # 2. 使用配置中的设置
        if not adapter:
            settings = getattr(self.cfg_mgr.cfg, "module_adapter_settings", {}).get("fetch", {})
            mode = settings.get("mode", "auto")
            
            if mode == "auto":
                adapter = self.registry.find_adapter_by_url(pid)
                if not adapter:
                    fallback = settings.get("fallback")
                    if fallback:
                        adapter = self.registry.get_adapter(fallback)
                    else:
                        adapter = self.registry.get_default_adapter(OJCapability.FETCH_PROBLEM)
            else:
                adapter = self.registry.get_adapter(settings.get("adapter"))
        
        # 对于 manual 适配器，设置用户隔离的工作区目录
        if adapter and adapter.name == "manual" and hasattr(adapter, 'set_workspace_dir'):
            adapter.set_workspace_dir(self._get_workspace_base())
        
        self._adapter_cache[pid] = adapter
        return adapter
    
    def _get_upload_adapter(self):
        """获取上传适配器（确保设置用户上下文）"""
        settings = getattr(self.cfg_mgr.cfg, "module_adapter_settings", {}).get("upload", {})
        name = settings.get("adapter")
        if name:
            adapter = self.registry.get_adapter(name)
            if adapter:
                # 确保每次使用时都更新 user_id（适配器是共享的）
                adapter._context = adapter._context or {}
                adapter._context['user_id'] = self.user_id
            return adapter
        return None
    
    def _get_submit_adapter(self):
        """获取提交适配器（确保设置用户上下文）"""
        settings = getattr(self.cfg_mgr.cfg, "module_adapter_settings", {}).get("submit", {})
        name = settings.get("adapter")
        if name:
            adapter = self.registry.get_adapter(name)
            if adapter:
                # 确保每次使用时都更新 user_id（适配器是共享的）
                adapter._context = adapter._context or {}
                adapter._context['user_id'] = self.user_id
            return adapter
        return None
    
    def _get_cached_auth(self, adapter_name: str):
        """获取缓存的认证（用户隔离）
        
        每个用户有独立的认证缓存，同一用户的并发任务共享认证
        """
        if self._user_context:
            auth_cache = self._user_context.get_auth(adapter_name)
            if auth_cache:
                # 返回 OJAuth 兼容对象
                return type('OJAuth', (), {
                    'token': auth_cache.token,
                    'session': auth_cache.session
                })()
        return None
    
    def _cache_auth(self, adapter_name: str, auth: Any):
        """缓存认证（用户隔离）
        
        同一用户的并发任务可以共享此认证
        """
        if self._user_context and auth:
            token = getattr(auth, 'token', str(auth))
            session = getattr(auth, 'session', None)
            self._user_context.set_auth(adapter_name, token, session)
    
    # ==================== 主执行流程 ====================
    
    def is_cancelled(self) -> bool:
        """检查是否已取消（内部CancelToken或外部回调）"""
        if self.cancel.cancelled():
            return True
        if self._cancellation_check and self._cancellation_check():
            return True
        return False
    
    def request_cancel(self):
        """请求取消"""
        self.cancel.cancel()
    
    def run(self, ids: List[str], modules: Dict[str, bool], 
            force_process_finished: bool = False,
            extra_settings: Optional[Dict] = None) -> List[TaskResult]:
        """批量执行任务"""
        try:
            if not ids:
                logger.warning("题目列表为空")
                return []
            
            # 过滤已完成的题目（除非强制处理）
            ids_to_process = ids
            if not force_process_finished:
                ids_to_process = [pid for pid in ids if not self._is_completed(pid)]
                skipped = len(ids) - len(ids_to_process)
                if skipped > 0:
                    logger.info(f"跳过 {skipped} 个已完成题目")
                    self._append_log(f"[SYSTEM] 跳过 {skipped} 个已完成题目")
            
            if not ids_to_process:
                logger.info("所有题目已完成")
                return []
            
            logger.info(f"开始处理 {len(ids_to_process)} 个题目")
            
            # 发布开始事件
            self.event_bus.publish_sync(TaskEvent(
                type=EventType.TASK_STARTED,
                task_id="batch",
                message=f"开始处理 {len(ids_to_process)} 个题目"
            ))
            
            # 创建结果容器
            results: List[TaskResult] = []
            id_to_row = {pid: i for i, pid in enumerate(ids_to_process)}
            
            # 并发执行
            max_workers = self.cfg_mgr.cfg.max_workers
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._run_one_task, pid, modules, id_to_row[pid]): pid
                    for pid in ids_to_process
                }
                
                for future in as_completed(futures):
                    pid = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"任务异常 {pid}: {e}")
                        results.append(TaskResult(original_id=pid, extra={"error": str(e)}))
            
            # 生成汇总
            self._generate_summary(results)
            
            # 发布完成事件
            success = sum(1 for r in results if r.ok_solve or r.ok_upload or r.ok_gen)
            self.event_bus.publish_sync(TaskEvent(
                type=EventType.TASK_COMPLETED,
                task_id="batch",
                message=f"完成 {success}/{len(results)}"
            ))
            
            return results
        finally:
            # 确保用户上下文计数在任何情况下都会减少
            if self._user_context:
                self._user_context.decrement_task()
    
    def _run_one_task(self, pid: str, modules: Dict[str, bool], row: int) -> TaskResult:
        """执行单个任务"""
        start = time.time()
        result = TaskResult(original_id=pid)
        cfg = self.cfg_mgr.cfg
        
        try:
            self.per_logs[pid] = []
            self._append_log(f"[{pid}] ========== 开始执行 ==========")
            
            # 记录配置信息
            self._append_log(f"[{pid}] 配置: 模块={modules}")
            self._append_log(f"[{pid}] 配置: 生成温度={getattr(cfg, 'temperature_generation', 0.3)}, 求解温度={getattr(cfg, 'temperature_solution', 0.3)}")
            self._append_log(f"[{pid}] 配置: 最大重试=3, 工作目录={self._problem_dir_for(pid)}")
            
            self._emit_status(row, {"fetch": "进行中"})
            
            if self.is_cancelled():
                self._append_log(f"[{pid}] 任务已取消")
                self._emit_status(row, {"fetch": "已取消"})
                self._flush_log_events(pid)
                self._flush_file_buffer(pid)  # 确保日志写入文件
                return result
            
            pdir = self._problem_dir_for(pid)
            pdir.mkdir(parents=True, exist_ok=True)
            
            # 1. 拉取题面
            if modules.get("fetch", True):
                self._update_stage(pid, "fetch")
                
                # 检查是否可以复用已有题面数据（必须是 AC 通过的）
                existing_data = ProblemDataManager.load(pdir)
                is_ac = ProblemDataManager.is_completed(pdir)  # ok_solve=True
                if existing_data and existing_data.get("title") and is_ac:
                    self._append_log(f"[{pid}] [FETCH] ✓ 复用已AC题面数据: {existing_data.get('title', 'N/A')}")
                    self._emit_status(row, {"fetch": "复用"})
                elif existing_data and existing_data.get("title"):
                    # 有数据但未AC，仍然复用题面（避免重复拉取）
                    self._append_log(f"[{pid}] [FETCH] ✓ 复用已有题面数据: {existing_data.get('title', 'N/A')}")
                    self._emit_status(row, {"fetch": "复用"})
                else:
                    self._append_log(f"[{pid}] [FETCH] 开始拉取题面...")
                    try:
                        fetch_adapter = self._get_fetch_adapter(pid)
                        if not fetch_adapter:
                            raise RuntimeError("无法获取拉取适配器")
                        
                        self._append_log(f"[{pid}] [FETCH] 使用适配器: {fetch_adapter.name}")
                        
                        fetcher = fetch_adapter.get_problem_fetcher()
                        if not fetcher:
                            raise RuntimeError(f"适配器 {fetch_adapter.name} 不支持拉取")
                        
                        parsed_id = fetcher.parse_problem_id(pid)
                        self._append_log(f"[{pid}] [FETCH] 解析题目ID: {pid} -> {parsed_id}")
                        
                        fetch_start = time.time()
                        problem_data = fetcher.fetch_problem(parsed_id)
                        fetch_elapsed = time.time() - fetch_start
                        
                        ProblemDataManager.save(pdir, problem_data)
                        
                        # 详细记录题目信息
                        title = problem_data.get('title', 'N/A')
                        time_limit = problem_data.get('time_limit', 'N/A')
                        memory_limit = problem_data.get('memory_limit', 'N/A')
                        content_len = len(problem_data.get('description', ''))
                        samples_count = len(problem_data.get('samples', []))
                        
                        self._append_log(f"[{pid}] [FETCH] ✓ 题面获取成功 (耗时 {fetch_elapsed:.2f}s)")
                        self._append_log(f"[{pid}] [FETCH]   标题: {title}")
                        self._append_log(f"[{pid}] [FETCH]   时限: {time_limit}, 内存: {memory_limit}")
                        self._append_log(f"[{pid}] [FETCH]   题面长度: {content_len} 字符, 样例数: {samples_count}")
                        self._emit_status(row, {"fetch": "成功"})
                    except Exception as e:
                        if "不存在" in str(e) or "404" in str(e):
                            self._append_log(f"[{pid}] [FETCH] ✗ 题号不存在")
                            self._emit_status(row, {"fetch": "失败(不存在)"})
                            self._flush_log_events(pid)
                            self._flush_file_buffer(pid)  # 确保日志写入文件
                            return result
                        self._append_log(f"[{pid}] [FETCH] ✗ 拉取失败: {e}")
                        raise
            else:
                self._append_log(f"[{pid}] [FETCH] 跳过（未启用）")
                self._emit_status(row, {"fetch": "跳过"})
            
            # 检查取消
            if self.is_cancelled():
                self._append_log(f"[{pid}] 任务已取消")
                self._flush_log_events(pid)
                self._flush_file_buffer(pid)  # 确保日志写入文件
                return result
            
            # ===== 远端题目预检测（如果启用上传，先检查远端是否已有同名题目）=====
            if modules.get("upload", False):
                try:
                    problem_data_file = pdir / "problem_data.json"
                    if problem_data_file.exists():
                        with open(problem_data_file, 'r', encoding='utf-8') as f:
                            prob_data = json.load(f)
                        title = prob_data.get('title', '').strip()
                        
                        if title:
                            upload_adapter = self._get_upload_adapter()
                            if upload_adapter and upload_adapter.name.lower() == 'hydrooj':
                                self._append_log(f"[{pid}] [CHECK] 检查远端是否已有同名题目...")
                                
                                hydrooj_auth = upload_adapter.login()
                                uploader = upload_adapter.get_data_uploader()
                                
                                # 精确标题搜索
                                if hasattr(uploader, '_search_exact_title'):
                                    existing_id = uploader._search_exact_title(title, hydrooj_auth)
                                    id_source = "搜索"
                                    
                                    # 回退机制：如果精确搜索失败，检查已保存的 real_id
                                    if not existing_id:
                                        saved_real_id = ProblemDataManager.get_upload_real_id(pdir, upload_adapter.name)
                                        if saved_real_id:
                                            try:
                                                from core.database import get_database
                                                db = get_database()
                                                adapter_config = db.get_user_adapter_config(self.user_id, upload_adapter.name)
                                                base_url = adapter_config.get("base_url", "")
                                                domain = adapter_config.get("domain", "")
                                                
                                                if base_url and domain:
                                                    verify_url = f"{base_url.rstrip('/')}/d/{domain}/p/{saved_real_id}"
                                                    verify_r = hydrooj_auth.session.get(verify_url, timeout=10, headers={
                                                        'User-Agent': 'Mozilla/5.0'
                                                    })
                                                    
                                                    if verify_r.status_code == 200 and title in verify_r.text:
                                                        existing_id = saved_real_id
                                                        id_source = "缓存"
                                            except Exception as verify_err:
                                                logger.debug(f"[{pid}] 验证已保存ID失败: {verify_err}")
                                    
                                    if existing_id:
                                        # 远端已有相同题目，直接跳过所有后续环节
                                        result.ok_gen = True
                                        result.ok_upload = True
                                        result.ok_solve = True  # 跳过求解
                                        
                                        # 保存 real_id
                                        ProblemDataManager.set_upload_real_id(pdir, upload_adapter.name, str(existing_id))
                                        
                                        # 构建 uploaded_url
                                        uploaded_url = None
                                        try:
                                            from core.database import get_database
                                            db = get_database()
                                            adapter_config = db.get_user_adapter_config(self.user_id, upload_adapter.name)
                                            base_url = adapter_config.get("base_url", "")
                                            domain = adapter_config.get("domain", "")
                                            if base_url and domain:
                                                uploaded_url = f"{base_url.rstrip('/')}/d/{domain}/p/{existing_id}"
                                                result.extra["uploaded_url"] = uploaded_url
                                        except Exception as url_err:
                                            logger.debug(f"构建上传URL失败: {url_err}")
                                        
                                        # 简洁日志
                                        self._append_log(f"[{pid}] [CHECK] ✓ 远端已有题目 (ID: {existing_id})，跳过全部环节")
                                        if uploaded_url:
                                            self._append_log(f"[{pid}] [CHECK] 题目链接: {uploaded_url}")
                                        
                                        # 标记完成并直接返回
                                        result.elapsed = time.time() - start
                                        self._mark_completed(pid, result)
                                        self._emit_status(row, {"gen": "跳过", "upload": "跳过", "solve": "跳过"})
                                        self._append_log(f"[{pid}] ========== 任务完成（远端已有）==========")
                                        self._append_log(f"[{pid}] 总耗时: {result.elapsed:.1f}s")
                                        self._flush_log_events(pid)
                                        self._flush_file_buffer(pid)  # 确保日志写入文件
                                        return result
                                    else:
                                        self._append_log(f"[{pid}] [CHECK] 远端无同名题目，继续正常流程")
                except Exception as e:
                    logger.debug(f"[{pid}] 远端预检测失败: {e}")
                    self._append_log(f"[{pid}] [CHECK] 预检测失败: {e}，继续正常流程")
            
            # 2. 生成测试数据（含本地验题）
            if modules.get("gen", False):
                self._update_stage(pid, "gen")
                
                # 检查是否可以复用已有测试数据（必须是 AC 通过的）
                existing_zip = self._zip_path_for(pid)
                is_ac = ProblemDataManager.is_completed(pdir)  # ok_solve=True
                
                if existing_zip.exists() and is_ac:
                    # AC 通过的测试数据可以复用
                    zip_size = existing_zip.stat().st_size
                    test_count = len(list((pdir / "tests").glob("*.in"))) if (pdir / "tests").exists() else 0
                    
                    self._append_log(f"[{pid}] [GEN] ✓ 复用已AC测试数据")
                    self._append_log(f"[{pid}] [GEN]   ZIP文件: {existing_zip} ({zip_size} bytes)")
                    self._append_log(f"[{pid}] [GEN]   测试点数量: {test_count}")
                    self._emit_status(row, {"gen": "复用"})
                    
                    result.ok_gen = True
                    result.extra["zip_path"] = str(existing_zip)
                else:
                    # 需要生成新的测试数据
                    self._append_log(f"[{pid}] [GEN] 开始生成测试数据...")
                    self._emit_status(row, {"gen": "进行中"})
                    
                    gen_temp = getattr(cfg, "temperature_generation", 0.3)
                    gen_context = []
                    gen_success = False
                    
                    self._append_log(f"[{pid}] [GEN] 初始温度: {gen_temp}, 最大重试: 3")
                    
                    for attempt in range(1, 4):
                        self._append_log(f"[{pid}] [GEN] 第 {attempt}/3 次尝试 (温度={gen_temp:.2f})")
                        gen_start = time.time()
                        try:
                            generator = self.services.create_generator()
                            gen_pdir, zip_path = generator.generate_for(
                                pid, temperature=gen_temp, context_history=gen_context
                            )
                            gen_elapsed = time.time() - gen_start
                            
                            if zip_path and Path(zip_path).exists():
                                zip_size = Path(zip_path).stat().st_size
                                test_count = len(list((pdir / "tests").glob("*.in"))) if (pdir / "tests").exists() else 0
                                
                                self._append_log(f"[{pid}] [GEN] ✓ 数据生成成功 (耗时 {gen_elapsed:.2f}s)")
                                self._append_log(f"[{pid}] [GEN]   ZIP文件: {zip_path} ({zip_size} bytes)")
                                self._append_log(f"[{pid}] [GEN]   测试点数量: {test_count}")
                                
                                # === 本地验题（作为生成的一部分）===
                                cpp_file = pdir / "solution.cpp"
                                test_dir = pdir / "tests"
                                
                                if cpp_file.exists() and test_dir.exists():
                                    cpp_size = cpp_file.stat().st_size
                                    self._append_log(f"[{pid}] [GEN] 开始本地验题...")
                                    self._append_log(f"[{pid}] [GEN]   代码文件: solution.cpp ({cpp_size} bytes)")
                                    self._append_log(f"[{pid}] [GEN]   测试点: {test_count} 个")
                                    
                                    # 使用并发控制
                                    from services.concurrency_manager import get_concurrency_manager
                                    concurrency_mgr = get_concurrency_manager()
                                    
                                    val_start = time.time()
                                    try:
                                        with concurrency_mgr.compile_context(timeout=120.0):
                                            val_result = self.services.validation_service.validate_solution(
                                                cpp_file, test_dir, pid
                                            )
                                    except TimeoutError:
                                        self._append_log(f"[{pid}] [GEN] 等待编译队列超时，重试...")
                                        raise Exception("编译队列等待超时")
                                    
                                    val_elapsed = time.time() - val_start
                                    
                                    if val_result.passed:
                                        self._append_log(f"[{pid}] [GEN] ✓ 本地验题通过 ({val_result.passed_cases}/{val_result.total_cases}, 耗时 {val_elapsed:.2f}s)")
                                        ProblemDataManager.set_validation_result(pdir, {
                                            "passed": True,
                                            "total_cases": val_result.total_cases,
                                            "passed_cases": val_result.passed_cases
                                        })
                                        
                                        result.ok_gen = True
                                        result.extra["zip_path"] = zip_path
                                        result.extra["validation_passed"] = True
                                        gen_success = True
                                        
                                        self._emit_status(row, {"gen": "成功"})
                                        break
                                    else:
                                        # 本地验题失败，继续重试生成
                                        self._append_log(f"[{pid}] [GEN] ✗ 本地验题失败 ({val_result.passed_cases}/{val_result.total_cases}, 耗时 {val_elapsed:.2f}s)")
                                        if hasattr(val_result, 'failed_cases') and val_result.failed_cases:
                                            for fc in val_result.failed_cases[:2]:  # 最多显示2个
                                                self._append_log(f"[{pid}] [GEN]   失败样例: {fc.case_name} - {fc.reason}")
                                        
                                        # 保存上下文用于下次重试
                                        gen_context.append({
                                            "attempt": attempt,
                                            "error": f"本地验题失败: {val_result.passed_cases}/{val_result.total_cases} 通过",
                                            "temperature": gen_temp,
                                            "validation_failed": True
                                        })
                                        
                                        # 验题失败降温
                                        old_temp = gen_temp
                                        gen_temp = max(0.1, gen_temp - 0.15)
                                        self._append_log(f"[{pid}] [GEN] 验题失败，降温: {old_temp:.2f} -> {gen_temp:.2f}")
                                        
                                        if attempt < 3:
                                            wait_time = 20 + random.uniform(-2, 2)
                                            self._append_log(f"[{pid}] [GEN] 等待 {wait_time:.1f}s 后重新生成...")
                                            if not interruptible_sleep(wait_time, self.is_cancelled):
                                                self._append_log(f"[{pid}] 任务已取消")
                                                return result
                                        continue
                                else:
                                    # 没有 solution.cpp，无法验题但数据生成成功
                                    self._append_log(f"[{pid}] [GEN] ⚠ 无题解代码，跳过本地验题")
                                    result.ok_gen = True
                                    result.extra["zip_path"] = zip_path
                                    gen_success = True
                                    self._emit_status(row, {"gen": "成功(未验题)"})
                                    break
                                    
                        except Exception as e:
                            gen_elapsed = time.time() - gen_start
                            error = str(e)
                            
                            self._append_log(f"[{pid}] [GEN] ✗ 第 {attempt} 次失败 (耗时 {gen_elapsed:.2f}s): {error[:100]}")
                            
                            # 保存上下文
                            gen_context.append({
                                "attempt": attempt,
                                "error": error[:200],
                                "temperature": gen_temp
                            })
                            
                            # CE降温策略
                            if "CE" in error or "compile" in error.lower():
                                old_temp = gen_temp
                                gen_temp = max(0.1, gen_temp - 0.2)
                                self._append_log(f"[{pid}] [GEN] 检测到编译错误，降温: {old_temp:.2f} -> {gen_temp:.2f}")
                            
                            if attempt < 3:
                                wait_time = 30 + random.uniform(-1.5, 1.5)
                                self._append_log(f"[{pid}] [GEN] 等待 {wait_time:.1f}s 后重试...")
                                if not interruptible_sleep(wait_time, self.is_cancelled):
                                    self._append_log(f"[{pid}] 任务已取消")
                                    return result
                            else:
                                self._append_log(f"[{pid}] [GEN] ✗ 已达最大重试次数，生成失败")
                                self._emit_status(row, {"gen": "失败"})
                    
                    if not gen_success:
                        self._append_log(f"[{pid}] [GEN] 生成失败，跳过后续步骤")
                        self._emit_status(row, {"upload": "跳过", "solve": "跳过"})
                        return result
            else:
                self._append_log(f"[{pid}] [GEN] 跳过（未启用）")
                self._emit_status(row, {"gen": "跳过"})
            
            # 检查取消
            if self.is_cancelled():
                self._append_log(f"[{pid}] 任务已取消")
                return result
            
            # 3. 上传（本地验题已在GEN阶段完成）
            if modules.get("upload", False):
                self._append_log(f"[{pid}] [UPLOAD] 开始上传流程...")
                zip_path = result.extra.get("zip_path") or str(self._zip_path_for(pid))
                
                if not Path(zip_path).exists():
                    self._append_log(f"[{pid}] [UPLOAD] ✗ ZIP文件不存在: {zip_path}")
                    self._emit_status(row, {"upload": "跳过(无文件)"})
                else:
                    self._update_stage(pid, "upload")
                    self._emit_status(row, {"upload": "进行中"})
                    
                    # 检查本地验题是否已通过（GEN阶段验证）
                    validation_passed = result.extra.get("validation_passed", False)
                    if not validation_passed:
                        # 如果GEN阶段没有验题，这里补充验题
                        cpp_file = pdir / "solution.cpp"
                        test_dir = pdir / "tests"
                        
                        if cpp_file.exists() and test_dir.exists():
                            self._append_log(f"[{pid}] [UPLOAD] 执行补充验题...")
                            
                            from services.concurrency_manager import get_concurrency_manager
                            concurrency_mgr = get_concurrency_manager()
                            
                            val_start = time.time()
                            try:
                                with concurrency_mgr.compile_context(timeout=120.0):
                                    val_result = self.services.validation_service.validate_solution(
                                        cpp_file, test_dir, pid
                                    )
                                val_elapsed = time.time() - val_start
                                
                                if not val_result.passed:
                                    self._append_log(f"[{pid}] [UPLOAD] ✗ 验题失败 ({val_result.passed_cases}/{val_result.total_cases}, 耗时 {val_elapsed:.2f}s)")
                                    self._emit_status(row, {"upload": "跳过(验题失败)"})
                                    return result
                                else:
                                    self._append_log(f"[{pid}] [UPLOAD] ✓ 验题通过 ({val_result.passed_cases}/{val_result.total_cases})")
                            except TimeoutError:
                                self._append_log(f"[{pid}] [UPLOAD] ⚠ 编译队列等待超时，继续上传...")
                    
                    # 上传数据
                    upload_adapter = self._get_upload_adapter()
                    if upload_adapter:
                        self._append_log(f"[{pid}] [UPLOAD] 使用适配器: {upload_adapter.name}")
                        self._append_log(f"[{pid}] [UPLOAD] ZIP文件: {zip_path}")
                        
                        # 上传重试机制
                        max_upload_retries = 3
                        upload_success = False
                        
                        for upload_attempt in range(1, max_upload_retries + 1):
                            try:
                                upload_start = time.time()
                                uploader = UploadService(
                                    upload_adapter, self.sems,
                                    log_callback=self._append_log
                                )
                                up_resp = uploader.upload_and_update(None, pid, zip_path)
                                upload_elapsed = time.time() - upload_start
                                
                                resp_code = up_resp.get("response", {}).get("code")
                                result.ok_upload = resp_code in (0, 200)
                                
                                if result.ok_upload:
                                    self._append_log(f"[{pid}] [UPLOAD] ✓ 上传成功 (耗时 {upload_elapsed:.2f}s, 响应码={resp_code})")
                                    self._emit_status(row, {"upload": "成功"})
                                    
                                    # 提取并保存上传后的题目ID（用于后续求解）
                                    # 优先级：1. 顶层 real_id（SHSOJ 适配器） 2. 顶层 actual_id（SHSOJ 备用）
                                    #         3. response.real_id（HydroOJ 适配器格式）
                                    real_id = up_resp.get("real_id") or up_resp.get("actual_id")
                                    if not real_id:
                                        response_data = up_resp.get("response", {})
                                        real_id = response_data.get("real_id")
                                    
                                    # 如果找到了 real_id，确保是字符串类型并保存
                                    if real_id:
                                        real_id = str(real_id)  # 确保是字符串类型
                                        
                                        if upload_adapter:
                                            # 保存上传后的 real_id（用于后续求解）
                                            ProblemDataManager.set_upload_real_id(pdir, upload_adapter.name, real_id)
                                            self._append_log(f"[{pid}] [UPLOAD] 已保存 {upload_adapter.name} 题目ID: {real_id}")
                                            
                                            # 根据适配器构建题目URL（从用户配置读取）
                                            try:
                                                from core.database import get_database
                                                db = get_database()
                                                adapter_config = db.get_user_adapter_config(self.user_id, upload_adapter.name)
                                                base_url = adapter_config.get("base_url", "")
                                                domain = adapter_config.get("domain", "")
                                                if base_url and domain:
                                                    uploaded_url = f"{base_url.rstrip('/')}/d/{domain}/p/{real_id}"
                                                    result.extra["uploaded_url"] = uploaded_url
                                                    self._append_log(f"[{pid}] [UPLOAD] 题目链接: {uploaded_url}")
                                            except Exception as url_err:
                                                logger.debug(f"构建上传URL失败: {url_err}")
                                    elif upload_adapter:
                                        # 如果没有找到 real_id，记录警告（但不上传失败，因为可能适配器不支持）
                                        self._append_log(f"[{pid}] [UPLOAD] ⚠ 响应中无题目ID，求解功能可能受影响")
                                    
                                    upload_success = True
                                    break
                                else:
                                    self._append_log(f"[{pid}] [UPLOAD] ✗ 上传失败 (响应码={resp_code})")
                                    if upload_attempt < max_upload_retries:
                                        wait_time = 5 * upload_attempt
                                        self._append_log(f"[{pid}] [UPLOAD] 等待 {wait_time}s 后重试...")
                                        if not interruptible_sleep(wait_time, self.is_cancelled):
                                            return result
                            except Exception as e:
                                self._append_log(f"[{pid}] [UPLOAD] ✗ 上传异常 (尝试 {upload_attempt}/{max_upload_retries}): {e}")
                                if upload_attempt < max_upload_retries:
                                    wait_time = 5 * upload_attempt
                                    self._append_log(f"[{pid}] [UPLOAD] 等待 {wait_time}s 后重试...")
                                    if not interruptible_sleep(wait_time, self.is_cancelled):
                                        return result
                        
                        if not upload_success:
                            self._emit_status(row, {"upload": "失败"})
                    else:
                        self._append_log(f"[{pid}] [UPLOAD] ✗ 未配置上传适配器")
                        self._emit_status(row, {"upload": "跳过(无适配器)"})
            else:
                self._append_log(f"[{pid}] [UPLOAD] 跳过（未启用）")
                self._emit_status(row, {"upload": "跳过"})
            
            # 检查取消
            if self.is_cancelled():
                self._append_log(f"[{pid}] 任务已取消")
                return result
            
            # 4. 求解
            if modules.get("solve", False):
                self._update_stage(pid, "solve")
                self._append_log(f"[{pid}] [SOLVE] 开始远程求解流程...")
                self._emit_status(row, {"solve": "进行中"})
                
                # 检查上传是否失败（如果启用了上传但失败，则跳过求解）
                if modules.get("upload", False) and not result.ok_upload:
                    self._append_log(f"[{pid}] [SOLVE] ✗ 上传失败，跳过求解（无题目可提交）")
                    self._emit_status(row, {"solve": "跳过(上传失败)"})
                    # 不再重试，直接跳过
                elif not (submit_adapter := self._get_submit_adapter()):
                    self._append_log(f"[{pid}] [SOLVE] ✗ 未配置提交适配器")
                    self._emit_status(row, {"solve": "跳过(无适配器)"})
                else:
                    # 如果刚完成上传，等待一段时间让服务器处理题目更新（避免"题目不存在"错误）
                    if modules.get("upload", False) and result.ok_upload:
                        wait_after_upload = 3 + random.uniform(-0.5, 1.5)  # 等待 3-4.5 秒
                        self._append_log(f"[{pid}] [SOLVE] 刚完成上传，等待 {wait_after_upload:.1f}s 让服务器处理题目更新...")
                        if not interruptible_sleep(wait_after_upload, self.is_cancelled):
                            return result
                    self._append_log(f"[{pid}] [SOLVE] 使用适配器: {submit_adapter.name}")
                    
                    solve_temp = getattr(cfg, "temperature_solution", 0.3)
                    solve_context = []
                    
                    self._append_log(f"[{pid}] [SOLVE] 初始温度: {solve_temp}, 最大重试: 3")
                    
                    for attempt in range(1, 4):
                        self._append_log(f"[{pid}] [SOLVE] 第 {attempt}/3 次尝试 (温度={solve_temp:.2f})")
                        solve_start = time.time()
                        try:
                            # 获取或创建认证
                            auth = self._get_cached_auth(submit_adapter.name)
                            if not auth and hasattr(submit_adapter, 'login'):
                                self._append_log(f"[{pid}] [SOLVE] 正在登录 {submit_adapter.name}...")
                                auth = submit_adapter.login()
                                if auth:
                                    self._cache_auth(submit_adapter.name, auth)
                                    self._append_log(f"[{pid}] [SOLVE] 登录成功，已缓存认证")
                            
                            solver = SolveService(
                                None, self.services.llm_solve,
                                self._get_workspace_base(), self.sems,
                                log_callback=self._append_log,
                                solution_searcher=self.services.solution_searcher,
                                summary_llm=self.services.llm_summary,
                                cancel_check=self.is_cancelled,
                                user_id=self.user_id  # 传递用户ID用于适配器配置隔离
                            )
                            
                            solve_result = solver.solve(
                                auth, pid,
                                temperature=solve_temp,
                                context_history=solve_context,
                                submit_adapter=submit_adapter
                            )
                            solve_elapsed = time.time() - solve_start
                            
                            # 检查是否被取消
                            if solve_result.get("cancelled"):
                                self._append_log(f"[{pid}] [SOLVE] 任务被取消")
                                return result
                            
                            final_status = solve_result.get("final", {}).get("status")
                            final_msg = solve_result.get("final", {}).get("message", "")
                            submission_id = solve_result.get("submission_id", "N/A")
                            
                            self._append_log(f"[{pid}] [SOLVE] 提交结果: status={final_status}, msg={final_msg}, id={submission_id}")
                            
                            if final_status == 0:  # AC
                                result.ok_solve = True
                                self._append_log(f"[{pid}] [SOLVE] ✓ AC成功! (耗时 {solve_elapsed:.2f}s)")
                                self._emit_status(row, {"solve": "成功"})
                                break
                            elif final_status in (6, -2):  # CE
                                old_temp = solve_temp
                                solve_temp = max(0.3, solve_temp - 0.2)
                                self._append_log(f"[{pid}] [SOLVE] ✗ 编译错误 (CE)，降温: {old_temp:.2f} -> {solve_temp:.2f}")
                            else:
                                status_name = {1: "WA", 2: "TLE", 3: "MLE", 4: "RE", 7: "PAC"}.get(final_status, str(final_status))
                                self._append_log(f"[{pid}] [SOLVE] ✗ 结果: {status_name} (耗时 {solve_elapsed:.2f}s)")
                                solve_context.append({"status": status_name, "attempt": attempt})
                            
                            if attempt < 3:
                                wait_time = 30 + random.uniform(-1.5, 1.5)
                                self._append_log(f"[{pid}] [SOLVE] 等待 {wait_time:.1f}s 后重试...")
                                if not interruptible_sleep(wait_time, self.is_cancelled):
                                    self._append_log(f"[{pid}] 任务已取消")
                                    self._flush_log_events(pid)
                                    self._flush_file_buffer(pid)  # 确保日志写入文件
                                    return result
                            else:
                                self._append_log(f"[{pid}] [SOLVE] ✗ 已达最大重试次数，求解失败")
                                self._emit_status(row, {"solve": f"失败"})
                                
                        except Exception as e:
                            solve_elapsed = time.time() - solve_start
                            error_msg = str(e)
                            self._append_log(f"[{pid}] [SOLVE] ✗ 第 {attempt} 次异常 (耗时 {solve_elapsed:.2f}s): {error_msg[:100]}")
                            
                            # 检查是否是特定错误（需要特殊处理）
                            is_rate_limit = "频率过快" in error_msg or "频率" in error_msg or "403" in error_msg
                            is_problem_not_exist = "不存在" in error_msg or "已不存在" in error_msg
                            # 检测 401 认证失效错误（SHSOJ 返回 "登录状态已失效"）
                            is_auth_expired = (
                                "401" in error_msg or 
                                "登录状态已失效" in error_msg or 
                                "登录失效" in error_msg or
                                "请重新登录" in error_msg or
                                "token" in error_msg.lower() and "expired" in error_msg.lower()
                            )
                            
                            if attempt < 3:
                                # 根据错误类型决定等待时间和处理方式
                                if is_auth_expired:
                                    # 认证失效：清除缓存认证，下次循环会重新登录
                                    self._append_log(f"[{pid}] [SOLVE] 检测到认证失效，清除缓存认证并重新登录...")
                                    if self._user_context:
                                        self._user_context.clear_auth(submit_adapter.name)
                                    # 下次循环时 _get_cached_auth() 会返回 None，自动触发重新登录
                                    wait_time = 2 + random.uniform(0, 1)  # 短暂等待后重试
                                    self._append_log(f"[{pid}] [SOLVE] 等待 {wait_time:.1f}s 后重新登录重试...")
                                elif is_rate_limit:
                                    # 频率限制：等待更长时间（60-90秒）
                                    wait_time = 60 + random.uniform(-5, 30)
                                    self._append_log(f"[{pid}] [SOLVE] 检测到频率限制错误，等待 {wait_time:.1f}s 后重试...")
                                elif is_problem_not_exist:
                                    # 题目不存在：可能是刚更新，等待服务器处理（15-25秒）
                                    wait_time = 15 + random.uniform(-2, 10)
                                    self._append_log(f"[{pid}] [SOLVE] 检测到题目不存在错误，等待 {wait_time:.1f}s 让服务器处理...")
                                else:
                                    # 其他错误：正常等待（30秒左右）
                                    wait_time = 30 + random.uniform(-1.5, 1.5)
                                    self._append_log(f"[{pid}] [SOLVE] 等待 {wait_time:.1f}s 后重试...")
                                
                                if not interruptible_sleep(wait_time, self.is_cancelled):
                                    self._append_log(f"[{pid}] 任务已取消")
                                    self._flush_log_events(pid)
                                    self._flush_file_buffer(pid)
                                    return result
                            else:
                                self._append_log(f"[{pid}] [SOLVE] ✗ 已达最大重试次数，求解失败")
                                self._emit_status(row, {"solve": "失败"})
            else:
                self._append_log(f"[{pid}] [SOLVE] 跳过（未启用）")
                self._emit_status(row, {"solve": "跳过"})
            
            result.elapsed = time.time() - start
            
            # 标记完成状态
            if result.ok_solve:
                self._mark_completed(pid, result)
            
            # 详细汇总（先刷新待发布的日志事件和文件缓冲区）
            self._flush_log_events(pid)
            self._flush_file_buffer(pid)  # 确保日志写入文件
            self._append_log(f"[{pid}] ========== 任务完成 ==========")
            self._append_log(f"[{pid}] 总耗时: {result.elapsed:.1f}s")
            check, cross = '✓', '✗'
            self._append_log(f"[{pid}] 结果: 生成={check if result.ok_gen else cross}, 上传={check if result.ok_upload else cross}, 求解={check if result.ok_solve else cross}")
            if result.extra.get('error'):
                self._append_log(f"[{pid}] 错误: {result.extra['error'][:100]}")
            self._append_log(f"[{pid}] ========================================")
            self._flush_log_events(pid)  # 确保最后一条日志也被发布
            self._flush_file_buffer(pid)  # 确保最终日志写入文件
            
        except Exception as e:
            logger.exception(f"任务失败 {pid}: {e}")
            result.extra["error"] = str(e)
            self._append_log(f"[{pid}] ✗ 执行失败: {e}")
            result.elapsed = time.time() - start
            # 确保异常日志也写入文件
            self._flush_log_events(pid)
            self._flush_file_buffer(pid)
        
        return result
    
    def _generate_summary(self, results: List[TaskResult]):
        """生成汇总报告"""
        import csv
        try:
            # JSON
            Path("summary.json").write_text(
                json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            
            # CSV
            with open("summary.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["problem_id", "gen", "upload", "solve", "elapsed"])
                for r in results:
                    w.writerow([r.original_id, r.ok_gen, r.ok_upload, r.ok_solve, f"{r.elapsed:.1f}"])
            
            # 失败列表
            failed = [r.original_id for r in results if not r.ok_solve]
            if failed:
                Path("failed_problems.txt").write_text("\n".join(failed), encoding="utf-8")
            
            logger.info("汇总已保存")
        except Exception as e:
            logger.error(f"生成汇总失败: {e}")
    
    def retry_single_module(self, pid: str, module: str) -> TaskResult:
        """重试单个模块"""
        modules = {
            "fetch": module == "fetch",
            "gen": module == "gen",
            "upload": module == "upload",
            "solve": module == "solve"
        }
        return self._run_one_task(pid, modules, 0)


# 兼容性导出
PipelineRunnerV7 = PipelineRunner
PipelineRunnerV8 = PipelineRunner
PipelineCLI = PipelineRunner
