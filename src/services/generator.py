# -*- coding: utf-8 -*-
# 题面数据生成：拉取题面 -> 组织提示词 -> DeepSeek 生成 gen.py -> 执行 -> 产出 zip
# 逻辑参考用户旧 getdata.py 的结构并进行健壮化  fileciteturn0file0

from __future__ import annotations

import subprocess, sys, json, time, threading, re
from pathlib import Path
from typing import Dict, Any, Tuple, List, TYPE_CHECKING

from loguru import logger

from utils.text import html_to_text, sanitize_code, sanitize_filename, parse_examples, samples_to_xml, samples_to_problem_format
from utils.concurrency import acquire, SemaphorePool
from services.oj_api import OJApi
from services.oj_adapter import OJApiAdapter
from services.llm.base import BaseLLMClient
from services.llm.stream_handler import StreamHandler
from services.llm.response_formatter import ResponseFormatter
from services.prompt_manager import get_prompt_manager
if TYPE_CHECKING:
    from services.image_service import ImageProcessResult

def build_prompt(problem: Dict[str, Any], pid: str, 
                 image_result: 'ImageProcessResult' = None,
                 reference_solutions: str = None) -> str:
    """构建生成数据的提示词
    
    Args:
        problem: 题目数据
        pid: 题目ID
        image_result: 图片处理结果（可选，由 ImageService 提供）
        reference_solutions: 参考题解（可选）
        
    Returns:
        提示词文本
    """
    parts = []
    title = problem.get("title") or ""
    desc_raw = problem.get("description") or ""
    input_raw = problem.get("input") or problem.get("inputFormat") or ""
    output_raw = problem.get("output") or problem.get("outputFormat") or ""
    hint_raw = problem.get("hint") or ""
    
    # 转换HTML为文本
    desc = html_to_text(desc_raw)
    input_fmt = html_to_text(input_raw)
    output_fmt = html_to_text(output_raw)
    hint = html_to_text(hint_raw)
    
    # 解析样例（分离输入输出）
    examples_raw = ""
    for field in ["examples", "samples", "sample"]:
        if problem.get(field):
            examples_raw = problem.get(field)
            break
    
    examples = parse_examples(examples_raw) if examples_raw else ""
    
    # 构建题面
    parts.append(f"# {title}\n")
    if desc: 
        parts.append("## 题目描述")
        parts.append(desc)
    
    # 插入OCR结果（如果有图片处理结果）
    if image_result and image_result.ocr_sections:
        parts.append("\n## 图片内容")
        parts.extend(image_result.ocr_sections)
    
    if input_fmt: 
        parts.append("\n## 输入格式")
        parts.append(input_fmt)
    if output_fmt: 
        parts.append("\n## 输出格式")
        parts.append(output_fmt)
    if examples: 
        parts.append("\n## 样例")
        parts.append(examples)
    if hint: 
        parts.append("\n## 提示")
        parts.append(hint)
    
    statement = "\n".join(parts)
    
    # 添加参考题解（如果有）
    if reference_solutions:
        statement += reference_solutions
    
    # 获取任务指令
    pm = get_prompt_manager()
    task_instructions = pm.get_data_generation_task_instructions(pid)
    
    return f"**【题面】**\n{statement}\n\n---\n\n" + task_instructions


class GeneratorService:
    def __init__(self, oj: OJApi, llm_client: BaseLLMClient, ocr_client: BaseLLMClient, 
                 workspace: Path, sems: SemaphorePool | None = None, 
                 log_callback=None, code_exec_timeout_sec: int = 300, 
                 solution_searcher=None, summary_llm: BaseLLMClient = None,
                 solve_llm_client: BaseLLMClient = None):
        self.oj = oj  # 保留向后兼容
        self._oj_port = OJApiAdapter(oj)  # 内部使用Port抽象
        self.llm_client = llm_client  # 用于生成测试数据代码
        self.ocr_client = ocr_client  # 用于OCR
        self.summary_llm = summary_llm  # 用于总结搜索结果
        self.solve_llm_client = solve_llm_client or llm_client  # 用于生成题解代码，默认使用生成客户端
        self.workspace = workspace
        self.sems = sems
        self.log_callback = log_callback or (lambda msg: None)
        self.code_exec_timeout_sec = code_exec_timeout_sec
        self.solution_searcher = solution_searcher
        self.formatter = ResponseFormatter()  # 响应格式化器

    def _log(self, pid: str, msg: str):
        """记录日志到文件和回调（不要重复写入）"""
        # 只调用log_callback，让pipeline统一处理
        self.log_callback(f"[{pid}] {msg}")

    def _get_canonical_id(self, pid: str) -> str:
        """获取规范化的题目ID（使用统一的ProblemIdResolver）"""
        try:
            from services.problem_id import get_problem_id_resolver
            resolver = get_problem_id_resolver()
            return resolver.canonicalize(pid)
        except Exception as e:
            logger.warning(f"[{pid}] 解析ID异常: {e}")
            return pid
    
    def generate_for(self, original_id: str, temperature: float = 0.7, context_history: list = None, 
                     image_result: 'ImageProcessResult' = None) -> Tuple[Path, str]:
        # 使用统一的规范化ID计算逻辑
        canonical_id = self._get_canonical_id(original_id)
        
        # 目录使用规范化ID（适配器+ID，精简格式）
        safe_pid = sanitize_filename(canonical_id)
        pdir = self.workspace / f"problem_{safe_pid}"
        pdir.mkdir(parents=True, exist_ok=True)
        
        # 清理旧数据
        tests_dir = pdir / "tests"
        
        # zip文件名使用完整URL（安全化后），便于追溯原始来源
        safe_url = sanitize_filename(original_id)
        zip_name = f"problem_{safe_url}_testcase.zip"
        zip_path = pdir / zip_name
        
        if tests_dir.exists():
            import shutil
            self._log(original_id, "清理旧的测试数据目录...")
            shutil.rmtree(tests_dir)
        
        if zip_path.exists():
            self._log(original_id, "删除旧的zip文件...")
            zip_path.unlink()

        self._log(original_id, "开始获取题面...")
        problem = None
        
        # 1. 优先检查本地是否已有题面数据（复用fetch模块拉取的结果）
        json_file = pdir / "problem_data.json"
        if json_file.exists():
            try:
                self._log(original_id, "检测到本地题面数据，直接复用...")
                problem_data = json.loads(json_file.read_text(encoding="utf-8"))
                
                # 使用公共方法转换样例格式
                samples_list = problem_data.get("samples", [])
                sample_format = samples_to_problem_format(samples_list, problem_data.get("hints"))
                
                # 转换为GeneratorService期望的格式
                problem = {
                    "title": problem_data.get("title", ""),
                    "description": problem_data.get("description", ""),
                    "input": problem_data.get("input_format", ""),
                    "inputFormat": problem_data.get("input_format", ""),
                    "output": problem_data.get("output_format", ""),
                    "outputFormat": problem_data.get("output_format", ""),
                    "hint": sample_format["hint"],
                    "examples": sample_format["examples"],
                    "samples": sample_format["samples"],
                    "timeLimit": problem_data.get("time_limit"),
                    "memoryLimit": problem_data.get("memory_limit"),
                }
                self._log(original_id, "✓ 复用本地题面数据成功")
            except Exception as e:
                logger.debug(f"[{original_id}] 读取本地题面数据失败: {e}，将重新拉取")
                problem = None
        
        # 2. 如果本地没有，尝试使用适配器系统（支持多OJ）
        if problem is None:
            try:
                from services.oj.registry import get_global_registry
                from services.oj.base.capabilities import OJCapability
                
                registry = get_global_registry()
                adapter = registry.find_adapter_by_url(original_id)
                
                if adapter and OJCapability.FETCH_PROBLEM in adapter.capabilities:
                    fetcher = adapter.get_problem_fetcher()
                    if fetcher:
                        # 解析题目ID
                        problem_id = fetcher.parse_problem_id(original_id)
                        if problem_id:
                            self._log(original_id, f"使用适配器 {adapter.display_name} 获取题面...")
                            if self.sems:
                                with acquire(self.sems.oj):
                                    problem_data = fetcher.fetch_problem(problem_id)
                            else:
                                problem_data = fetcher.fetch_problem(problem_id)
                            
                            # 保存题面数据到本地，供后续复用
                            json_file = pdir / "problem_data.json"
                            json_file.write_text(
                                json.dumps(problem_data, ensure_ascii=False, indent=2),
                                encoding="utf-8"
                            )
                            
                            # 使用公共方法转换样例格式
                            samples_list = problem_data.get("samples", [])
                            sample_format = samples_to_problem_format(samples_list, problem_data.get("hints"))
                            
                            # 转换为GeneratorService期望的格式
                            problem = {
                                "title": problem_data.get("title", ""),
                                "description": problem_data.get("description", ""),
                                "input": problem_data.get("input_format", ""),
                                "inputFormat": problem_data.get("input_format", ""),
                                "output": problem_data.get("output_format", ""),
                                "outputFormat": problem_data.get("output_format", ""),
                                "hint": sample_format["hint"],
                                "examples": sample_format["examples"],
                                "samples": sample_format["samples"],
                                "timeLimit": problem_data.get("time_limit"),
                                "memoryLimit": problem_data.get("memory_limit"),
                            }
                            self._log(original_id, f"✓ 使用适配器 {adapter.display_name} 获取题面成功，已保存到本地")
            except Exception as e:
                logger.debug(f"[{original_id}] 适配器获取题面失败，尝试旧API: {e}")
                problem = None
        
        # 如果没有通过适配器获取到题面，使用旧的OJApi（向后兼容SHSOJ）
        if problem is None:
            try:
                self._log(original_id, "使用SHSOJ API获取题面...")
                if self.sems: 
                    with acquire(self.sems.oj):
                        problem = self._oj_port.get_problem_detail(original_id)
                else:
                    problem = self._oj_port.get_problem_detail(original_id)
                self._log(original_id, "✓ 使用SHSOJ API获取题面成功")
            except Exception as e:
                self._log(original_id, f"✗ 获取题面失败: {e!r}")
                raise

        # 搜索现有题解（传递题目信息以提高准确性）
        reference_solutions = None
        if self.solution_searcher:
            try:
                title = problem.get("title", "")
                desc = problem.get("description", "")
                reference_solutions = self.solution_searcher.search_solutions(
                    None, original_id, 
                    title=title,
                    description=desc,
                    summary_llm=getattr(self, 'summary_llm', None)
                )
                if reference_solutions:
                    self._log(original_id, "✓ 找到并处理参考题解")
            except Exception as e:
                self._log(original_id, f"搜索题解失败: {e!r}")
                logger.debug(f"[{original_id}] 搜索题解异常: {e}")
        
        try:
            self._log(original_id, "开始构建提示词...")
            # prompt中使用规范化ID（适配器+ID格式），便于LLM理解
            statement = build_prompt(problem, canonical_id,
                                    image_result=image_result,
                                    reference_solutions=reference_solutions)
            
            # 添加历史上下文（如果有）
            if context_history:
                context_str = "\n\n--- 历史尝试记录 ---\n"
                for i, ctx in enumerate(context_history[-2:], 1):  # 最多保留最近2次
                    context_str += f"\n**尝试 {ctx.get('attempt', i)}**:\n"
                    if 'error' in ctx:
                        context_str += f"错误: {ctx['error']}\n"
                    if 'code_snippet' in ctx:
                        context_str += f"生成的代码片段:\n```python\n{ctx['code_snippet'][:500]}...\n```\n"
                context_str += "\n请根据上述历史尝试避免相同的错误，生成正确的代码。\n"
                statement += context_str
                self._log(original_id, f"已添加{len(context_history)}次历史上下文")
            
            self._log(original_id, f"提示词构建成功，长度: {len(statement)} 字符")
        except Exception as e:
            self._log(original_id, f"构建提示词失败: {e!r}")
            logger.exception(f"[{original_id}] build_prompt 异常详情:")
            raise
        
        try:
            self._log(original_id, "开始保存提示词到文件...")
            (pdir / "problem_statement.txt").write_text(statement, encoding="utf-8")
            (pdir / "prompt.txt").write_text(statement, encoding="utf-8")
            self._log(original_id, "提示词已保存到文件")
        except Exception as e:
            self._log(original_id, f"保存提示词失败: {e!r}")
            logger.exception(f"[{original_id}] 保存文件异常详情:")
            raise

        # 调用LLM（流式模式）
        try:
            self._log(original_id, f"调用 {self.llm_client.get_provider_name()} 生成 gen.py（流式模式）...")
            self._log(original_id, "--- 开始思考过程 ---")
        except Exception as e:
            self._log(original_id, f"准备LLM调用失败: {e!r}")
            logger.exception(f"[{original_id}] 准备异常:")
            raise
        
        # 使用StreamHandler处理流式输出（传入log_callback实现实时推送）
        stream_handler = StreamHandler(pdir / "problem.log", log_callback=self.log_callback)
        
        try:
            self._log(original_id, f"正在连接 {self.llm_client.get_provider_name()} API...")
            self._log(original_id, f"使用temperature={temperature}")
            pm = get_prompt_manager()
            system_prompt = pm.get_data_generation_system_prompt()
            
            if self.sems:
                with acquire(self.sems.ds):
                    content, reasoning = self.llm_client.chat_completion(
                        statement, stream=True, 
                        on_chunk=lambda r, c: stream_handler.on_chunk(r, c, original_id), 
                        system_prompt=system_prompt,
                        temperature=temperature
                    )
            else:
                content, reasoning = self.llm_client.chat_completion(
                    statement, stream=True, 
                    on_chunk=lambda r, c: stream_handler.on_chunk(r, c, original_id),
                    system_prompt=system_prompt,
                    temperature=temperature
                )
            
            self._log(original_id, f"{self.llm_client.get_provider_name()} API 调用成功")
            self._log(original_id, "--- 思考过程结束 ---")
            self._log(original_id, f"代码生成完成，共 {len(content)} 字符")
        except KeyboardInterrupt:
            self._log(original_id, "用户中断")
            raise
        except Exception as e:
            provider_name = self.llm_client.get_provider_name()
            self._log(original_id, f"{provider_name}调用失败: {e!r}")
            logger.exception(f"[{original_id}] {provider_name}异常详情:")
            raise
        finally:
            try:
                stream_handler.flush(original_id)
            except Exception as e:
                logger.debug(f"[{original_id}] StreamHandler flush error: {e}")
        
        if reasoning:
            self._log(original_id, f"推理过程完成（共 {len(reasoning)} 字符）")
        
        # 如果content为空但reasoning有内容，尝试提取
        if not content and reasoning:
            self._log(original_id, "警告：content为空，尝试从reasoning提取代码...")
            code_blocks = re.findall(r'```(?:python|py)?\s*(.*?)```', reasoning, re.DOTALL | re.IGNORECASE)
            if code_blocks:
                content = code_blocks[-1].strip()
                self._log(original_id, f"从reasoning提取到代码（{len(content)}字符）")
            else:
                self._log(original_id, "错误：无法从reasoning提取代码")
                provider_name = self.llm_client.get_provider_name()
                raise RuntimeError(f"{provider_name}未返回有效代码（content为空且无法从reasoning提取）")

        # 使用canonical_id（适配器+ID格式）用于prompt中的PROBLEM_ID显示
        code = sanitize_code(content, canonical_id)
        
        # 手动替换zip文件名为完整URL格式（安全化后）
        # sanitize_code中的zip替换使用的是规范化ID，这里需要覆盖为完整URL
        safe_url = sanitize_filename(original_id)
        code = re.sub(
            r'problem_[^_\s"]+_testcase\.zip',
            f'problem_{safe_url}_testcase.zip',
            code
        )
        
        (pdir / "gen.py").write_text(code, encoding="utf-8")
        self._log(original_id, f"gen.py 已保存（{len(code)} 字符）")

        # 语法预检查，如失败则尝试从content/reasoning提取最后代码块重试一次
        def _try_compile(py_code: str) -> tuple[bool, str]:
            try:
                compile(py_code, "gen.py", "exec")
                return True, ""
            except SyntaxError as se:
                return False, f"{se.__class__.__name__}: {se}"
            except Exception as e:
                return False, f"{e.__class__.__name__}: {e}"

        ok_compile, compile_err = _try_compile(code)
        if not ok_compile:
            # 重试：从原始content和reasoning中提取最后一个python代码块
            self._log(original_id, f"首次语法检查失败，尝试重提取代码并修正：{compile_err}")
            try:
                # 优先从 content 中提取，失败则从 reasoning
                blocks = re.findall(r'```(?:python|py)?\s*(.*?)```', content or "", re.DOTALL | re.IGNORECASE)
                if not blocks and reasoning:
                    blocks = re.findall(r'```(?:python|py)?\s*(.*?)```', reasoning or "", re.DOTALL | re.IGNORECASE)
                if blocks:
                    retry_code = blocks[-1].strip()
                    retry_code = sanitize_code(retry_code, canonical_id)
                    # 再次覆盖zip名为完整URL安全化格式
                    safe_url_retry = sanitize_filename(original_id)
                    retry_code = re.sub(
                        r'problem_[^_\s"]+_testcase\.zip',
                        f'problem_{safe_url_retry}_testcase.zip',
                        retry_code
                    )
                    (pdir / "gen.py").write_text(retry_code, encoding="utf-8")
                    ok_compile, compile_err = _try_compile(retry_code)
                    code = retry_code if ok_compile else code  # 仅在成功时替换
            except Exception as _:
                # 忽略重试过程中的异常，继续使用原始code
                pass
            if not ok_compile:
                self._log(original_id, f"警告：gen.py 语法检查仍失败：{compile_err}")
        
        if len(code) < 100:
            self._log(original_id, f"警告：生成的代码很短（{len(code)}字符），可能不完整")
            raise RuntimeError(f"生成的gen.py太短（{len(code)}字符），可能生成失败")

        # 执行
        self._log(original_id, "开始执行 gen.py 生成测试数据...")
        out_path = pdir / "gen_output.txt"
        err_path = pdir / "gen_error.txt"
        try:
            t0 = time.time()
            proc = subprocess.run([sys.executable, "gen.py"], cwd=pdir, capture_output=True, text=True, timeout=self.code_exec_timeout_sec)
            (pdir / "gen.returncode").write_text(str(proc.returncode), encoding="utf-8")
            elapsed = time.time() - t0
            (pdir / "gen.elapsed").write_text(f"{elapsed:.2f}", encoding="utf-8")
            
            # 分别保存stdout和stderr
            if proc.stdout:
                out_path.write_text(proc.stdout, encoding="utf-8")
            if proc.stderr:
                err_path.write_text(proc.stderr, encoding="utf-8")
            
            self._log(original_id, f"gen.py 执行完成，退出码 {proc.returncode}，耗时 {elapsed:.2f}s")
            
            if proc.returncode != 0:
                self._log(original_id, f"✗ gen.py 返回非零退出码: {proc.returncode}")
                # 输出详细错误信息
                if proc.stdout:
                    self._log(original_id, f"stdout前500字符: {proc.stdout[:500]}")
                if proc.stderr:
                    self._log(original_id, f"stderr前500字符: {proc.stderr[:500]}")
        except subprocess.TimeoutExpired:
            self._log(original_id, "错误：gen.py 执行超时（15分钟）")
            raise
        except Exception as e:
            self._log(original_id, f"错误：执行 gen.py 出错: {e!r}")
            raise

        # 校验
        self._log(original_id, "校验生成的测试数据...")
        tests_dir = pdir / "tests"
        # 先进行一次后处理：只去掉文件开头和结尾的空白行，保留行内的前导空格
        # 这对于字符串图案题（如输出字母圣诞树）非常重要
        if (tests_dir.exists()):
            try:
                for f in tests_dir.glob("*.*"):
                    if f.suffix in (".in", ".out"):
                        try:
                            content_txt = f.read_text(encoding="utf-8")
                            # 只去掉开头的空白行和结尾的空白行，保留行内的前导空格
                            lines = content_txt.splitlines(keepends=True)
                            # 去掉开头的空行（只去掉完全空白的行）
                            while lines and not lines[0].strip():
                                lines.pop(0)
                            # 去掉结尾的空行（只去掉完全空白的行）
                            while lines and not lines[-1].strip():
                                lines.pop(-1)
                            trimmed = "".join(lines)
                            # 保持换行风格简单一致：末尾加单个换行符，避免无换行导致的判定差异
                            if trimmed and not trimmed.endswith("\n"):
                                trimmed += "\n"
                            f.write_text(trimmed, encoding="utf-8")
                        except Exception:
                            # 单文件失败不影响整体流程
                            continue
            except Exception:
                pass
        ok = tests_dir.exists() and all((tests_dir / f"{i}.in").exists() and (tests_dir / f"{i}.out").exists() for i in range(10))
        
        if ok:
            self._log(original_id, "✓ 所有测试数据文件已生成（0..9.in/out）")
        else:
            missing = []
            for i in range(10):
                if not (tests_dir / f"{i}.in").exists():
                    missing.append(f"{i}.in")
                if not (tests_dir / f"{i}.out").exists():
                    missing.append(f"{i}.out")
            if missing:
                self._log(original_id, f"警告：缺少文件 {', '.join(missing)}")
        
        # 规范化空输入文件（避免后端无法解析0字节的.in文件）
        if tests_dir.exists():
            normalized_count = 0
            for i in range(10):
                in_file = tests_dir / f"{i}.in"
                if in_file.exists() and in_file.stat().st_size == 0:
                    # 将完全空的.in文件改写为包含单个换行符
                    in_file.write_text("\n", encoding="utf-8")
                    normalized_count += 1
            if normalized_count > 0:
                self._log(original_id, f"规范化 {normalized_count} 个空输入文件 (0字节 → 1字节换行符)")
        
        # zip文件名使用完整URL（安全化后）
        safe_url = sanitize_filename(original_id)
        zip_name = f"problem_{safe_url}_testcase.zip"
        zip_path = pdir / zip_name
        
        # 总是重新打包（已在开始时删除旧zip）
        self._log(original_id, "打包测试数据为 zip...")
        if tests_dir.exists() and ok:
            import zipfile
            with zipfile.ZipFile(zip_path, "w") as z:
                count = 0
                for i in range(10):
                    for ext in ("in", "out"):
                        f = tests_dir / f"{i}.{ext}"
                        if f.exists():
                            z.write(f, arcname=f.name)
                            count += 1
            self._log(original_id, f"✓ zip 打包完成（包含 {count} 个文件）")
        else:
            self._log(original_id, "✗ 测试数据不完整，无法打包")
        
        if not zip_path.exists():
            self._log(original_id, f"错误：未生成 zip 文件")
            raise RuntimeError(f"[{original_id}] 未生成 zip：{zip_path}")
        
        self._log(original_id, f"✓ 数据生成完成：{zip_path}")
        
        # 立即生成题解代码（solution.cpp）
        try:
            self._log(original_id, "开始生成题解代码...")
            solution_code = self._generate_solution_code(problem, canonical_id, pdir, temperature, reference_solutions)
            
            # 保存为 solution.cpp
            solution_file = pdir / "solution.cpp"
            solution_file.write_text(solution_code, encoding="utf-8")
            self._log(original_id, f"✓ 题解代码已保存：solution.cpp ({len(solution_code)} 字符)")
        except Exception as e:
            self._log(original_id, f"✗ 生成题解代码失败: {e}")
            logger.exception(f"[{original_id}] 生成题解异常:")
            # 不中断流程，继续返回
        
        return pdir, str(zip_path)
    
    def _generate_solution_code(self, problem: Dict[str, Any], problem_id: str, 
                                pdir: Path, temperature: float = 0.7,
                                reference_solutions: str = None) -> str:
        """生成题解代码（C++）
        
        Args:
            problem: 题目数据
            problem_id: 题目ID
            pdir: 工作目录
            temperature: LLM 温度
            reference_solutions: 参考题解
            
        Returns:
            C++ 代码字符串
        """
        from services.solver import build_prompt_for_solution
        from services.llm.response_formatter import ResponseFormatter
        from utils.text import sanitize_cpp_code
        
        # 构建题解提示词
        prompt = build_prompt_for_solution(problem, reference_solutions=reference_solutions)
        
        # 调用 Solve LLM 生成代码（使用 chat_completion）
        pm = get_prompt_manager()
        system_prompt = pm.get_solution_system_prompt()
        
        # 使用信号量（如果有）
        if self.sems:
            with acquire(self.sems.ds):
                content, reasoning = self.solve_llm_client.chat_completion(
                    prompt, 
                    stream=False,  # 不使用流式，简单获取结果
                    system_prompt=system_prompt,
                    temperature=temperature
                )
        else:
            content, reasoning = self.solve_llm_client.chat_completion(
                prompt, 
                stream=False,
                system_prompt=system_prompt,
                temperature=temperature
            )
        
        # 提取并清理 C++ 代码
        formatter = ResponseFormatter()
        try:
            # 使用 ResponseFormatter 的 extract_cpp_code 方法
            code = formatter.extract_cpp_code(content)
        except ValueError as e:
            # 如果提取失败，尝试直接清理全部内容
            logger.warning(f"[{problem_id}] extract_cpp_code 失败: {e}，尝试直接清理")
            code = sanitize_cpp_code(content)
            
            # 验证清理后的代码
            if not code or len(code.strip()) < 50:
                raise RuntimeError(f"无法从响应中提取有效的 C++ 代码（长度: {len(code.strip())}）")
        
        # 验证代码长度
        if len(code.strip()) < 50:
            raise RuntimeError(f"生成的题解代码太短（{len(code)} 字符）")
        
        return code
