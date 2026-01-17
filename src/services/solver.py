# -*- coding: utf-8 -*-
# 求解：按旧 solve.py 的思路，使用 DeepSeek 生成 C++ 并提交轮询  fileciteturn0file2

from __future__ import annotations

import time, json, threading
from pathlib import Path
from typing import Dict, Any

from loguru import logger

from utils.concurrency import acquire, SemaphorePool, interruptible_sleep
from services.oj_api import OJApi, OJAuth
from services.oj_adapter import OJApiAdapter
from services.llm.base import BaseLLMClient
from services.llm.stream_handler import StreamHandler
from services.prompt_manager import get_prompt_manager
from services.problem_data_manager import ProblemDataManager
from utils.text import html_to_text, sanitize_cpp_code, sanitize_filename, parse_examples
from services.oj.shsoj.status_codes import get_status_name, is_judging, is_final_status, is_compile_error, is_accepted


def build_prompt_for_solution(problem: Dict[str, Any], reference_solutions: str = None) -> str:
    title = problem.get("title", "")
    desc = html_to_text(problem.get("description", ""))
    input_fmt = html_to_text(problem.get("input") or problem.get("inputFormat") or "")
    output_fmt = html_to_text(problem.get("output") or problem.get("outputFormat") or "")
    
    # 解析样例（分离输入输出）
    examples_raw = ""
    for field in ["examples", "samples", "sample"]:
        if problem.get(field):
            examples_raw = problem.get(field)
            break
    
    examples = parse_examples(examples_raw) if examples_raw else ""
    hint = html_to_text(problem.get("hint", ""))
    
    prompt_parts = [
        f"# 题目：{title}\n",
        "## 题目描述",
        desc,
        "\n## 输入格式",
        input_fmt,
        "\n## 输出格式", 
        output_fmt,
    ]
    
    if examples:
        prompt_parts.extend(["\n## 样例", examples])
    if hint:
        prompt_parts.extend(["\n## 提示", hint])
    
    # 添加参考题解（如果有）
    if reference_solutions:
        prompt_parts.append(reference_solutions)
    
    # 获取任务要求
    pm = get_prompt_manager()
    task_requirements = pm.get_solution_task_requirements()
    prompt_parts.append(task_requirements)
    
    return "\n".join(prompt_parts)


class SolveService:
    # 类级别的 HydroOJ 认证对象，所有 SolveService 实例共享同一个 session（避免并发时创建多个 session 导致 403）
    _hydrooj_adapter = None
    _hydrooj_auth = None
    _hydrooj_auth_lock = threading.Lock()
    _hydrooj_auth_created_at: float = 0  # 认证创建时间戳
    _HYDROOJ_AUTH_TTL: float = 3600  # 认证有效期（秒），默认1小时
    
    @classmethod
    def _is_hydrooj_auth_expired(cls) -> bool:
        """检查 HydroOJ 认证是否过期"""
        if cls._hydrooj_auth is None:
            return True
        return (time.time() - cls._hydrooj_auth_created_at) > cls._HYDROOJ_AUTH_TTL
    
    @classmethod
    def _refresh_hydrooj_auth_if_needed(cls) -> bool:
        """如果认证过期则刷新，返回是否刷新成功"""
        with cls._hydrooj_auth_lock:
            if cls._is_hydrooj_auth_expired() and cls._hydrooj_adapter is not None:
                try:
                    cls._hydrooj_auth = cls._hydrooj_adapter.login()
                    cls._hydrooj_auth_created_at = time.time()
                    logger.info("[HydroOJ] 认证已刷新")
                    return True
                except Exception as e:
                    logger.warning(f"[HydroOJ] 认证刷新失败: {e}")
                    return False
            return True
    
    def __init__(self, oj: OJApi, llm_client: BaseLLMClient, workspace: Path, sems: SemaphorePool | None = None, 
                 log_callback=None, solution_searcher=None, summary_llm: BaseLLMClient = None,
                 cancel_check=None, user_id: int = None):
        self.oj = oj  # 保留向后兼容
        self._oj_port = OJApiAdapter(oj)  # 内部使用Port抽象
        self.llm_client = llm_client
        self.summary_llm = summary_llm  # 用于总结搜索结果
        self.workspace = workspace
        self.sems = sems
        self.log_callback = log_callback or (lambda msg: None)
        self.solution_searcher = solution_searcher
        self.cancel_check = cancel_check  # 取消检查函数
        self.user_id = user_id  # 用户ID，用于适配器配置隔离
    
    def _is_cancelled(self) -> bool:
        """检查是否被取消"""
        if self.cancel_check:
            return self.cancel_check()
        return False

    def _get_hydrooj_adapter_and_auth(self):
        """获取 HydroOJ 适配器和认证（确保正确的用户配置隔离）
        
        Returns:
            tuple: (adapter, auth) 或 (None, None) 如果获取失败
        """
        if not self.user_id:
            logger.warning("[SolveService] 未设置 user_id，无法获取 HydroOJ 适配器")
            return None, None
        
        try:
            from services.oj.registry import get_global_registry
            registry = get_global_registry()
            adapter = registry.get_adapter('hydrooj')
            
            if not adapter:
                logger.warning("[SolveService] 未找到 HydroOJ 适配器")
                return None, None
            
            # 设置用户上下文（确保使用正确的用户配置）
            adapter._context = adapter._context or {}
            adapter._context['user_id'] = self.user_id
            
            # 加载用户配置（每次都重新加载，确保配置隔离）
            adapter._ensure_config()
            
            # 获取或刷新认证
            with SolveService._hydrooj_auth_lock:
                # 检查认证是否过期或配置是否变化
                need_new_auth = (
                    SolveService._hydrooj_auth is None or
                    SolveService._is_hydrooj_auth_expired() or
                    # 如果适配器配置变化（不同用户），也需要重新认证
                    getattr(SolveService, '_hydrooj_auth_user_id', None) != self.user_id
                )
                
                if need_new_auth:
                    SolveService._hydrooj_auth = adapter.login()
                    SolveService._hydrooj_auth_created_at = time.time()
                    SolveService._hydrooj_auth_user_id = self.user_id
                    logger.debug(f"[SolveService] 创建 HydroOJ 认证 (user_id={self.user_id})")
                
                return adapter, SolveService._hydrooj_auth
                
        except Exception as e:
            logger.warning(f"[SolveService] 获取 HydroOJ 适配器失败: {e}")
            return None, None

    def _log(self, pid: str, msg: str):
        """记录日志（不要重复写入）"""
        # 只调用log_callback，让pipeline统一处理
        self.log_callback(f"[{pid}] {msg}")
    
    def _get_canonical_id(self, original_id: str) -> str:
        """获取规范化的题目ID（使用统一的ProblemIdResolver）"""
        try:
            from services.problem_id import get_problem_id_resolver
            resolver = get_problem_id_resolver()
            return resolver.canonicalize(original_id)
        except Exception as e:
            logger.debug(f"[{original_id}] 解析ID失败: {e}")
            return original_id

    def _generate_solution(self, original_id: str, prob: Dict[str, Any], pdir: Path, language: str = "C++",
                          reference_solutions: str = None, temperature: float = 0.7, reuse_existing: bool = True) -> str:
        """生成解题代码（可重试）
        
        Args:
            reuse_existing: 是否复用已存在的solution.cpp
        """
        # 检查是否已有solution.cpp（优先复用）
        cpp_file = pdir / "solution.cpp"
        if reuse_existing and cpp_file.exists():
            try:
                code = cpp_file.read_text(encoding='utf-8')
                if len(code) >= 50:  # 代码长度合理
                    self._log(original_id, f"复用已生成的 solution.cpp ({len(code)} 字符)")
                    return code
                else:
                    self._log(original_id, f"已有的 solution.cpp 太短({len(code)}字符)，重新生成...")
            except Exception as e:
                self._log(original_id, f"读取已有 solution.cpp 失败({e})，重新生成...")
        
        # 生成新代码
        prompt = build_prompt_for_solution(prob, reference_solutions=reference_solutions)
        self._log(original_id, f"调用 {self.llm_client.get_provider_name()} 生成 {language} 解答（流式模式）...")
        self._log(original_id, "--- 开始思考过程 ---")
        
        # 使用 StreamHandler 处理流式输出（支持实时回调推送）
        stream_handler = StreamHandler(pdir / "problem.log", log_callback=self.log_callback)
        
        pm = get_prompt_manager()
        system_prompt = pm.get_solution_system_prompt()
        
        self._log(original_id, f"使用temperature={temperature}")
        content, reasoning = "", None
        try:
            if self.sems:
                with acquire(self.sems.ds):
                    content, reasoning = self.llm_client.chat_completion(
                        prompt, stream=True, 
                        on_chunk=lambda r, c: stream_handler.on_chunk(r, c, original_id), 
                        system_prompt=system_prompt,
                        temperature=temperature
                    )
            else:
                content, reasoning = self.llm_client.chat_completion(
                    prompt, stream=True, 
                    on_chunk=lambda r, c: stream_handler.on_chunk(r, c, original_id), 
                    system_prompt=system_prompt,
                    temperature=temperature
                )
        finally:
            stream_handler.flush(original_id)
        
        self._log(original_id, "--- 思考过程结束 ---")
        self._log(original_id, f"代码生成完成，共 {len(content or '')} 字符")
        
        if reasoning:
            self._log(original_id, f"推理过程完成（共 {len(reasoning)} 字符）")
        
        code = content or ""
        
        if not code and reasoning:
            self._log(original_id, "尝试从reasoning中提取代码...")
            import re
            code_blocks = re.findall(r'```(?:cpp|c\+\+)?\s*(.*?)```', reasoning, re.DOTALL)
            if code_blocks:
                code = code_blocks[0].strip()
                self._log(original_id, f"从reasoning提取到代码（{len(code)}字符）")
        
        # 清洗代码
        code = sanitize_cpp_code(code)
        
        (pdir / "solution.cpp").write_text(code, encoding="utf-8")
        self._log(original_id, f"解答代码已保存（{len(code)} 字符）")
        
        if len(code) < 50:
            raise RuntimeError(f"生成的代码太短（{len(code)}字符），低于OJ最小要求（50字符）")
        
        return code
    
    def submit_only(self, auth: OJAuth, original_id: str, language: str = "C++", submit_adapter=None) -> Dict[str, Any]:
        """仅提交已有代码并轮询结果（用于频率限制后重试）"""
        canonical_id = self._get_canonical_id(original_id)
        safe_pid = sanitize_filename(canonical_id)
        pdir = self.workspace / f"problem_{safe_pid}"
        cpp_path = pdir / "solution.cpp"
        
        if not cpp_path.exists():
            raise RuntimeError(f"代码文件不存在: {cpp_path}")
        
        code = cpp_path.read_text(encoding="utf-8")
        self._log(original_id, f"读取已有代码（{len(code)} 字符）")
        
        solve_id = original_id
        
        # 如果提供了提交适配器，使用配置的适配器提交
        if submit_adapter:
            adapter_name = getattr(submit_adapter, 'name', 'unknown')
            adapter_display = getattr(submit_adapter, 'display_name', adapter_name)
            
            # 检查是否有该适配器的 real_id（用于提交）
            upload_real_id = ProblemDataManager.get_upload_real_id(pdir, adapter_name)
            if upload_real_id:
                solve_id = upload_real_id
                self._log(original_id, f"使用 {adapter_display} 题目ID: {upload_real_id}")
            else:
                # 没有 real_id，说明题目未上传到该平台
                raise RuntimeError(f"题目尚未上传到 {adapter_display}，请先启用「上传」模块")
            
            self._log(original_id, f"使用配置的适配器 {adapter_display} 重新提交代码...")
            
            try:
                # 获取提交器
                submitter = submit_adapter.get_solution_submitter()
                if not submitter:
                    raise RuntimeError(f"适配器 {adapter_display} 不支持提交功能")
                
                # 如果适配器需要认证，使用传入的auth或适配器自己的登录
                submit_auth = auth
                if submit_auth is None:
                    # 尝试适配器自己的登录方法
                    if hasattr(submit_adapter, 'login'):
                        self._log(original_id, f"适配器 {adapter_display} 需要登录，正在登录...")
                        submit_auth = submit_adapter.login()
                        if not submit_auth:
                            raise RuntimeError(f"适配器 {adapter_display} 登录失败")
                        self._log(original_id, f"✓ 适配器 {adapter_display} 登录成功")
                
                # 由适配器决定语言格式
                language_key = submitter.get_default_language("C++")
                
                # 提交代码
                submit_result = submitter.submit_solution(solve_id, code, language_key, submit_auth)
                
                if submit_result.get("status") == "success":
                    submit_id = submit_result.get("submission_id", "unknown")
                    self._log(original_id, f"✓ 提交成功，提交ID：{submit_id}")
                    if submit_result.get("record_url"):
                        self._log(original_id, f"记录页: {submit_result.get('record_url')}")
                    
                    # 查询判题状态
                    self._log(original_id, "查询判题状态...")
                    if not interruptible_sleep(3.0, self._is_cancelled):  # 等待判题开始
                        return {"cancelled": True}
                    
                    if submit_id and submit_id != "unknown":
                        status_result = submitter.get_submission_status(submit_id, submit_auth)
                        final_status_name = status_result.get("status", "Unknown")
                        score = status_result.get("score")
                        is_accepted = status_result.get("is_accepted", False)
                        
                        # 显示判题状态和分数
                        if score is not None:
                            self._log(original_id, f"判题状态: {final_status_name} ({score}分)")
                        else:
                            self._log(original_id, f"判题状态: {final_status_name}")
                        
                        # 返回结果
                        return {
                            "final": {
                                "status": 0 if is_accepted else 1,
                                "status_name": final_status_name,
                                "score": score
                            },
                            "submit_id": submit_id,
                            "adapter": adapter_name
                        }
                    else:
                        return {
                            "final": {"status": 1, "status_name": "Unknown"},
                            "submit_id": None,
                            "adapter": adapter_name
                        }
                else:
                    error_msg = submit_result.get("message", "提交失败")
                    raise RuntimeError(f"{adapter_display} 提交失败: {error_msg}")
                    
            except Exception as e:
                self._log(original_id, f"✗ {adapter_display} 提交失败: {e}")
                raise RuntimeError(f"{adapter_display} 提交失败: {e}")
        
        # 向后兼容：使用旧的 API（如果没有提供适配器）
        # 修改为C++ With O2
        language = "C++ With O2"
        
        # 检查是否有 HydroOJ 的 real_id
        hydrooj_real_id = ProblemDataManager.get_hydrooj_real_id(pdir)
        if hydrooj_real_id:
            solve_id = hydrooj_real_id
            logger.debug(f"[{original_id}] 使用 HydroOJ 题目ID: {hydrooj_real_id}")
        
        self._log(original_id, "重新提交代码到 OJ...")
        if self.sems:
            with acquire(self.sems.oj_write):
                submit_id = self._oj_port.submit_problem_judge(auth, solve_id, code, language=language)
        else:
            submit_id = self._oj_port.submit_problem_judge(auth, solve_id, code, language=language)
        
        self._log(original_id, f"✓ 提交成功，提交ID：{submit_id}")
        self._log(original_id, "开始轮询判题结果...")
        
        # 等待判题（可中断）
        if not interruptible_sleep(2.0, self._is_cancelled):
            self._log(original_id, "任务被取消")
            return {"cancelled": True}
        
        deadline = time.time() + 240
        last = {}
        poll_count = 0
        
        while time.time() < deadline:
            # 检查取消
            if self._is_cancelled():
                self._log(original_id, "任务被取消")
                return {"cancelled": True}
            
            if self.sems:
                with acquire(self.sems.oj):
                    sub = self._oj_port.get_submission_detail(auth, submit_id)
            else:
                sub = self._oj_port.get_submission_detail(auth, submit_id)
            last = sub
            status = sub.get("status")
            poll_count += 1
            
            status_name = get_status_name(status)
            self._log(original_id, f"[轮询 {poll_count}] {status_name}")
            
            if is_compile_error(status) and not last.get("errorMessage"):
                if poll_count < 3:
                    self._log(original_id, f"  CE但无错误信息，继续等待判题...")
                    if not interruptible_sleep(3.0, self._is_cancelled):
                        return {"cancelled": True}
                    continue
            
            if is_final_status(status):
                if is_accepted(status):
                    self._log(original_id, "✓ 判题通过 (Accepted)！")
                else:
                    self._log(original_id, f"✗ 判题未通过：{status_name}")
                    if is_compile_error(status):
                        error_msg = last.get("errorMessage", "无错误信息")
                        self._log(original_id, f"错误信息: {error_msg}")
                
                result_path = pdir / "solve_result.json"
                result_path.write_text(json.dumps({"final": last, "submit_id": submit_id}, ensure_ascii=False, indent=2), encoding="utf-8")
                self._log(original_id, "判题结果已保存")
                return {"final": last, "submit_id": submit_id}
            
            if not interruptible_sleep(3.0, self._is_cancelled):
                return {"cancelled": True}
        
        self._log(original_id, "✗ 判题超时（240秒）")
        return {"final": last, "submit_id": submit_id, "timeout": True}
    
    def solve(self, auth: OJAuth, original_id: str, language: str = "C++", temperature: float = 0.7, 
             context_history: list = None, submit_adapter=None) -> Dict[str, Any]:
        """求解题目
        
        Args:
            auth: OJ认证信息
            original_id: 题目原始ID（URL）
            language: 编程语言
            temperature: LLM温度参数
            context_history: 上下文历史（用于重试）
            submit_adapter: 提交适配器（如果提供，将优先使用此适配器提交，而不是根据hydrooj_real_id自动选择）
        """
        canonical_id = self._get_canonical_id(original_id)
        safe_pid = sanitize_filename(canonical_id)
        pdir = self.workspace / f"problem_{safe_pid}"
        pdir.mkdir(parents=True, exist_ok=True)

        # 检查是否有 HydroOJ 的 real_id（用于求解）
        solve_id = original_id
        use_local_problem = False
        hydrooj_real_id = ProblemDataManager.get_hydrooj_real_id(pdir)
        
        # 如果提供了提交适配器，优先使用配置的适配器，而不是根据hydrooj_real_id自动选择
        use_configured_adapter = submit_adapter is not None
        
        # 如果没有 real_id，尝试通过搜索找到题目（仅对 HydroOJ，且未使用配置的适配器时）
        if not hydrooj_real_id and not use_configured_adapter:
            # 如果本地有题面数据，尝试通过搜索找到 HydroOJ 题目
            prob_data_file = pdir / "problem_data.json"
            if prob_data_file.exists():
                try:
                    from services.oj.registry import get_global_registry
                    registry = get_global_registry()
                    if registry:
                        # 读取本地题面数据
                        prob_data = ProblemDataManager.load(pdir)
                        if prob_data:
                            title = prob_data.get('title', '')
                            tags = prob_data.get('tags', [])
                            
                            if title:
                                # 尝试通过搜索找到题目
                                self._log(original_id, "未找到 HydroOJ real_id，尝试通过搜索找到题目...")
                                
                                # 获取 HydroOJ 适配器和认证（使用正确的用户配置隔离）
                                hydrooj_adapter, hydrooj_auth = self._get_hydrooj_adapter_and_auth()
                                
                                if hydrooj_adapter and hydrooj_auth:
                                    try:
                                        uploader = hydrooj_adapter.get_data_uploader()
                                        
                                        # 调用搜索方法（支持标题和标签匹配）
                                        if hasattr(uploader, '_search_problem_by_title'):
                                            found_id = uploader._search_problem_by_title(title, hydrooj_auth, tags=tags if tags else None)
                                            if found_id:
                                                hydrooj_real_id = found_id
                                                # 保存 real_id
                                                ProblemDataManager.set_hydrooj_real_id(pdir, found_id)
                                                self._log(original_id, f"✓ 通过搜索找到 HydroOJ 题目ID: {found_id}")
                                            else:
                                                self._log(original_id, "⚠ 未找到匹配的 HydroOJ 题目（可能题目尚未上传）")
                                    except Exception as e:
                                        self._log(original_id, f"搜索 HydroOJ 题目失败: {e}")
                                        logger.debug(f"[{original_id}] 搜索 HydroOJ 题目异常: {e}", exc_info=True)
                except Exception as e:
                    logger.debug(f"[{original_id}] 搜索 HydroOJ 题目异常: {e}")
        
        if hydrooj_real_id:
            solve_id = hydrooj_real_id
            use_local_problem = True  # HydroOJ 题目使用本地数据
            self._log(original_id, f"HydroOJ 题目ID: {hydrooj_real_id}")

        # 获取题面数据
        # 优先使用本地数据：当有 HydroOJ real_id 或使用配置的提交适配器时，都应该用本地数据
        # 因为此时 solve_id 是 HydroOJ 上的题目ID，无法从 SHSOJ API 拉取
        if use_local_problem or use_configured_adapter:
            # 使用本地已保存的题面数据
            self._log(original_id, "使用本地题面数据...")
            prob_data = ProblemDataManager.load(pdir)
            if not prob_data:
                raise RuntimeError(f"无法加载本地题面数据: {pdir}，请确保已执行'拉取题面'步骤")
            prob = prob_data  # 使用本地数据
        else:
            # SHSOJ 题目：从 API 拉取
            self._log(original_id, "开始求解：拉取题面...")
            if self.sems:
                with acquire(self.sems.oj):
                    prob = self._oj_port.get_problem_detail(solve_id)
            else:
                prob = self._oj_port.get_problem_detail(solve_id)
            self._log(original_id, "题面获取成功")

        # 搜索现有题解（传递题目信息以提高准确性）
        reference_solutions = None
        if self.solution_searcher:
            try:
                title = prob.get("title", "")
                desc = prob.get("description", "")
                reference_solutions = self.solution_searcher.search_solutions(
                    auth, original_id,
                    title=title,
                    description=desc,
                    summary_llm=self.summary_llm
                )
                if reference_solutions:
                    self._log(original_id, "✓ 找到并处理参考题解")
            except Exception as e:
                self._log(original_id, f"搜索题解失败: {e!r}")
                logger.debug(f"[{original_id}] 搜索题解异常: {e}")

        # 生成或复用solution.cpp
        code = self._generate_solution(original_id, prob, pdir, language=language, 
                                       reference_solutions=reference_solutions, 
                                       temperature=temperature, reuse_existing=True)

        # 如果提供了提交适配器，使用配置的适配器提交
        if use_configured_adapter:
            # 使用配置的适配器提交
            adapter_name = getattr(submit_adapter, 'name', 'unknown')
            adapter_display = getattr(submit_adapter, 'display_name', adapter_name)
            
            # 检查是否有该适配器的 real_id（用于提交）
            upload_real_id = ProblemDataManager.get_upload_real_id(pdir, adapter_name)
            if upload_real_id:
                solve_id = upload_real_id
                self._log(original_id, f"使用 {adapter_display} 题目ID: {upload_real_id}")
            else:
                # 没有 real_id，说明题目未上传到该平台
                raise RuntimeError(f"题目尚未上传到 {adapter_display}，请先启用「上传」模块")
            
            self._log(original_id, f"使用配置的适配器 {adapter_display} 提交代码...")
            
            try:
                # 获取提交器
                submitter = submit_adapter.get_solution_submitter()
                if not submitter:
                    raise RuntimeError(f"适配器 {adapter_display} 不支持提交功能")
                
                # 如果适配器需要认证，使用传入的auth或适配器自己的登录
                submit_auth = auth
                if submit_auth is None:
                    # 尝试适配器自己的登录方法
                    if hasattr(submit_adapter, 'login'):
                        self._log(original_id, f"适配器 {adapter_display} 需要登录，正在登录...")
                        submit_auth = submit_adapter.login()
                        if not submit_auth:
                            raise RuntimeError(f"适配器 {adapter_display} 登录失败")
                        self._log(original_id, f"✓ 适配器 {adapter_display} 登录成功")
                
                # 由适配器决定语言格式
                language_key = submitter.get_default_language("C++")
                
                # 提交代码
                submit_result = submitter.submit_solution(solve_id, code, language_key, submit_auth)
                
                if submit_result.get("status") == "success":
                    submit_id = submit_result.get("submission_id", "unknown")
                    self._log(original_id, f"✓ 提交成功，提交ID：{submit_id}")
                    if submit_result.get("record_url"):
                        self._log(original_id, f"记录页: {submit_result.get('record_url')}")
                    
                    # 查询判题状态
                    self._log(original_id, "查询判题状态...")
                    if not interruptible_sleep(3.0, self._is_cancelled):  # 等待判题开始
                        return {"cancelled": True}
                    
                    if submit_id and submit_id != "unknown":
                        status_result = submitter.get_submission_status(submit_id, submit_auth)
                        final_status_name = status_result.get("status", "Unknown")
                        score = status_result.get("score")
                        is_accepted = status_result.get("is_accepted", False)
                        
                        # 显示判题状态和分数
                        if score is not None:
                            self._log(original_id, f"判题状态: {final_status_name} ({score}分)")
                        else:
                            self._log(original_id, f"判题状态: {final_status_name}")
                        
                        # 返回结果
                        return {
                            "final": {
                                "status": 0 if is_accepted else 1,
                                "status_name": final_status_name,
                                "score": score
                            },
                            "submit_id": submit_id,
                            "adapter": adapter_name
                        }
                    else:
                        return {
                            "final": {"status": 1, "status_name": "Unknown"},
                            "submit_id": None,
                            "adapter": adapter_name
                        }
                else:
                    error_msg = submit_result.get("message", "提交失败")
                    raise RuntimeError(f"{adapter_display} 提交失败: {error_msg}")
                    
            except Exception as e:
                self._log(original_id, f"✗ {adapter_display} 提交失败: {e}")
                raise RuntimeError(f"{adapter_display} 提交失败: {e}")
        # 检查是否是 HydroOJ 题目（use_local_problem 为 True 说明有 hydrooj_real_id）
        elif use_local_problem and hydrooj_real_id:
            # HydroOJ 题目：使用 HydroOJ 适配器提交（向后兼容）
            self._log(original_id, "提交代码到 HydroOJ...")
            try:
                # 获取 HydroOJ 适配器和认证（使用正确的用户配置隔离）
                hydrooj_adapter, hydrooj_auth = self._get_hydrooj_adapter_and_auth()
                
                if not hydrooj_adapter or not hydrooj_auth:
                    raise RuntimeError("无法获取 HydroOJ 适配器或认证，请检查用户配置")
                
                logger.debug(f"[{original_id}] 使用 HydroOJ 适配器: {hydrooj_adapter.base_url}, {hydrooj_adapter.domain}")
                
                # 获取提交器
                submitter = hydrooj_adapter.get_solution_submitter()
                
                # 由适配器决定语言格式
                language_key = submitter.get_default_language("C++")
                submit_result = submitter.submit_solution(solve_id, code, language_key, hydrooj_auth)
                
                if submit_result.get("status") == "success":
                    submit_id = submit_result.get("submission_id", "unknown")
                    self._log(original_id, f"✓ 提交成功，提交ID：{submit_id}")
                    self._log(original_id, f"记录页: {submit_result.get('record_url', '')}")
                    
                    # HydroOJ 使用轻量状态查询
                    self._log(original_id, "查询判题状态...")
                    if not interruptible_sleep(3.0, self._is_cancelled):  # 等待判题开始
                        return {"cancelled": True}
                    
                    if submit_id and submit_id != "unknown":
                        status_result = submitter.get_submission_status(submit_id, hydrooj_auth)
                        final_status_name = status_result.get("status", "Unknown")
                        score = status_result.get("score")
                        hydrooj_accepted = status_result.get("is_accepted", False)
                        
                        # 显示判题状态和分数
                        if score is not None:
                            self._log(original_id, f"判题状态: {final_status_name} ({score}分)")
                        else:
                            self._log(original_id, f"判题状态: {final_status_name}")
                        
                        # 返回结果（HydroOJ 格式）
                        return {
                            "final": {
                                "status": 0 if hydrooj_accepted else 1,
                                "status_name": final_status_name,
                                "score": score
                            },
                            "submit_id": submit_id,
                            "adapter": "hydrooj"
                        }
                    else:
                        return {
                            "final": {"status": 1, "status_name": "Unknown"},
                            "submit_id": None,
                            "adapter": "hydrooj"
                        }
                else:
                    error_msg = submit_result.get("message", "提交失败")
                    raise RuntimeError(f"HydroOJ 提交失败: {error_msg}")
                    
            except Exception as e:
                self._log(original_id, f"✗ HydroOJ 提交失败: {e}")
                raise RuntimeError(f"HydroOJ 提交失败: {e}")
        else:
            # SHSOJ 题目：使用原有逻辑
            language = "C++ With O2"
            
            self._log(original_id, "提交代码到 OJ...")
            if self.sems:
                with acquire(self.sems.oj_write):  # 使用写入信号量严格限流
                    submit_id = self._oj_port.submit_problem_judge(auth, solve_id, code, language=language)
            else:
                submit_id = self._oj_port.submit_problem_judge(auth, solve_id, code, language=language)
            self._log(original_id, f"✓ 提交成功，提交ID：{submit_id}")
            self._log(original_id, "开始轮询判题结果...")
            
            # 先等待2秒让OJ开始判题（可中断）
            if not interruptible_sleep(2.0, self._is_cancelled):
                return {"cancelled": True}
            
            deadline = time.time() + 240
            last = {}
            poll_count = 0
            
            while time.time() < deadline:
                # 检查取消
                if self._is_cancelled():
                    self._log(original_id, "任务被取消")
                    return {"cancelled": True}
                
                if self.sems:
                    with acquire(self.sems.oj):
                        sub = self._oj_port.get_submission_detail(auth, submit_id)
                else:
                    sub = self._oj_port.get_submission_detail(auth, submit_id)
                last = sub
                status = sub.get("status")
                poll_count += 1
                
                # 实时输出判题状态
                status_name = get_status_name(status)
                self._log(original_id, f"[轮询 {poll_count}] {status_name}")
                
                # 如果是CE但没有错误信息，可能是OJ还在处理，再等等
                if is_compile_error(status) and not last.get("errorMessage"):
                    if poll_count < 3:  # 前3次轮询到CE但无错误信息时继续等待
                        self._log(original_id, f"  CE但无错误信息，继续等待判题...")
                        if not interruptible_sleep(3.0, self._is_cancelled):
                            return {"cancelled": True}
                        continue
                
                if is_final_status(status):
                    if is_accepted(status):
                        self._log(original_id, "✓ 判题通过 (Accepted)！")
                    else:
                        self._log(original_id, f"✗ 判题未通过：{status_name}")
                        # 显示详细信息
                        if last.get("errorMessage"):
                            self._log(original_id, f"  错误信息: {last.get('errorMessage')}")
                    break
                
                if not interruptible_sleep(3.0, self._is_cancelled):  # 增加轮询间隔到3秒
                    return {"cancelled": True}
            
            if time.time() >= deadline:
                self._log(original_id, "警告：判题轮询超时（4分钟）")

            # 标准化返回格式，确保 final.status 字段存在
            # status=0 表示 Accepted，其他值表示失败
            final_status = 0 if is_accepted(last.get("status")) else last.get("status", -1)
            result = {
                "submitId": submit_id, 
                "final": {
                    "status": final_status,
                    "status_name": get_status_name(last.get("status")),
                    "raw": last  # 保留原始响应
                }
            }
            (pdir / "solve_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            self._log(original_id, "判题结果已保存")
            return result
