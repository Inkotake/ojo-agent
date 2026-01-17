# -*- coding: utf-8 -*-
"""代码验证服务 - 编译、运行、测试

支持跨平台（Windows/Linux）编译和运行
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import platform
import os

from loguru import logger


def _get_executable_suffix() -> str:
    """获取当前系统的可执行文件后缀"""
    return ".exe" if platform.system() == "Windows" else ""


@dataclass
class ValidationConfig:
    """验证配置"""
    compiler: str = "g++"
    compile_flags: List[str] = field(default_factory=lambda: ["-std=c++17", "-O2", "-Wall"])
    timeout: int = 10
    compile_timeout: int = 30
    comparison_mode: str = "ignore_trailing_spaces"  # strict, ignore_trailing_spaces, ignore_all_spaces


@dataclass
class CompileResult:
    """编译结果"""
    success: bool
    executable_path: Optional[Path] = None
    error_message: Optional[str] = None
    stderr: Optional[str] = None
    stdout: Optional[str] = None


@dataclass
class TestCaseResult:
    """单个测试用例结果"""
    case_name: str
    passed: bool
    reason: Optional[str] = None
    expected_output: Optional[str] = None
    actual_output: Optional[str] = None


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    total_cases: int
    passed_cases: int
    failed_cases: List[TestCaseResult] = field(default_factory=list)
    compile_result: Optional[CompileResult] = None
    executable_path: Optional[Path] = None


class ValidationService:
    """代码验证服务
    
    职责：
    - 编译 C++ 代码
    - 运行测试用例
    - 对比输出
    - 生成详细报告
    - 保存可执行文件供复用
    """
    
    def __init__(self, config: ValidationConfig = None):
        """初始化验证服务
        
        Args:
            config: 验证配置
        """
        self.config = config or ValidationConfig()
    
    def validate_solution(self, solution_file: Path, test_dir: Path, problem_id: str) -> ValidationResult:
        """验证解决方案
        
        完整流程：
        1. 编译代码
        2. 运行所有测试用例
        3. 对比输出
        4. 生成结果报告
        
        Args:
            solution_file: C++ 源文件路径
            test_dir: 测试数据目录
            problem_id: 题目 ID（用于日志）
            
        Returns:
            ValidationResult 验证结果
        """
        logger.debug(f"[验证服务] {problem_id} - 开始验证")
        
        # 编译代码（跨平台支持）
        executable_name = f"solution{_get_executable_suffix()}"
        executable_path = solution_file.parent / executable_name
        compile_result = self.compile_solution(solution_file, executable_path, problem_id)
        
        if not compile_result.success:
            logger.warning(f"[验证服务] {problem_id} - 编译失败")
            return ValidationResult(
                passed=False,
                total_cases=0,
                passed_cases=0,
                compile_result=compile_result,
                executable_path=None
            )
        
        # 运行测试用例
        test_result = self.run_tests(executable_path, test_dir, problem_id)
        
        # 构建结果
        passed = (test_result["passed_count"] == test_result["total_count"] 
                 and test_result["total_count"] > 0)
        
        logger.info(f"[验证服务] {problem_id} - 结果: {test_result['passed_count']}/{test_result['total_count']} 通过")
        
        return ValidationResult(
            passed=passed,
            total_cases=test_result["total_count"],
            passed_cases=test_result["passed_count"],
            failed_cases=test_result["failed_cases"],
            compile_result=compile_result,
            executable_path=executable_path if passed else None
        )
    
    def compile_solution(self, solution_file: Path, output_path: Path, problem_id: str) -> CompileResult:
        """编译 C++ 解决方案
        
        Args:
            solution_file: C++ 源文件
            output_path: 输出可执行文件路径
            problem_id: 题目 ID
            
        Returns:
            CompileResult 编译结果
        """
        try:
            logger.debug(f"[验证服务] {problem_id} - 编译: {solution_file.name}")
            
            # 构建编译命令
            cmd = [
                self.config.compiler,
                str(solution_file),
                "-o", str(output_path)
            ] + self.config.compile_flags
            
            # 执行编译
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.compile_timeout
            )
            
            if result.returncode == 0:
                logger.debug(f"[验证服务] {problem_id} - 编译成功")
                return CompileResult(
                    success=True,
                    executable_path=output_path,
                    stderr=result.stderr,
                    stdout=result.stdout
                )
            else:
                error_msg = result.stderr or result.stdout or "编译失败"
                logger.warning(f"[验证服务] {problem_id} - 编译失败: {error_msg[:200]}")
                return CompileResult(
                    success=False,
                    error_message=error_msg,
                    stderr=result.stderr,
                    stdout=result.stdout
                )
                
        except FileNotFoundError:
            error_msg = f"编译器 {self.config.compiler} 未找到，请确认已安装 MinGW 或 g++"
            logger.error(f"[验证服务] {problem_id} - {error_msg}")
            return CompileResult(
                success=False,
                error_message=error_msg
            )
        except subprocess.TimeoutExpired:
            error_msg = f"编译超时（{self.config.compile_timeout}秒）"
            logger.error(f"[验证服务] {problem_id} - {error_msg}")
            return CompileResult(
                success=False,
                error_message=error_msg
            )
        except Exception as e:
            error_msg = f"编译异常: {str(e)}"
            logger.error(f"[验证服务] {problem_id} - {error_msg}")
            return CompileResult(
                success=False,
                error_message=error_msg
            )
    
    def run_tests(self, executable: Path, test_dir: Path, problem_id: str) -> Dict[str, Any]:
        """运行所有测试用例
        
        Args:
            executable: 可执行文件路径
            test_dir: 测试数据目录
            problem_id: 题目 ID
            
        Returns:
            测试结果字典
        """
        test_files = sorted(test_dir.glob("*.in"))
        total_count = len(test_files)
        passed_count = 0
        failed_cases = []
        
        for test_file in test_files:
            case_name = test_file.stem
            out_file = test_dir / f"{case_name}.out"
            
            if not out_file.exists():
                logger.warning(f"[验证服务] {problem_id} - 缺少输出文件: {out_file.name}")
                continue
            
            # 运行单个测试用例
            case_result = self._run_single_test(executable, test_file, out_file, case_name, problem_id)
            
            if case_result.passed:
                passed_count += 1
            else:
                failed_cases.append(case_result)
        
        return {
            "total_count": total_count,
            "passed_count": passed_count,
            "failed_cases": failed_cases
        }
    
    def _run_single_test(self, executable: Path, input_file: Path, output_file: Path, 
                         case_name: str, problem_id: str) -> TestCaseResult:
        """运行单个测试用例
        
        Args:
            executable: 可执行文件
            input_file: 输入文件
            output_file: 期望输出文件
            case_name: 测试用例名称
            problem_id: 题目 ID
            
        Returns:
            TestCaseResult 测试用例结果
        """
        try:
            # 读取期望输出
            expected_output = output_file.read_text(encoding='utf-8').strip()
            
            # 读取输入
            test_input = input_file.read_text(encoding='utf-8')
            
            # 运行程序
            result = subprocess.run(
                [str(executable)],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=self.config.timeout
            )
            
            actual_output = result.stdout.strip()
            
            # 对比输出
            if self._compare_output(expected_output, actual_output):
                logger.debug(f"[验证服务] {problem_id} - 测试点 {case_name}: 通过")
                return TestCaseResult(
                    case_name=case_name,
                    passed=True
                )
            else:
                logger.debug(f"[验证服务] {problem_id} - 测试点 {case_name}: WA")
                return TestCaseResult(
                    case_name=case_name,
                    passed=False,
                    reason="输出不匹配",
                    expected_output=expected_output[:200] if len(expected_output) > 200 else expected_output,
                    actual_output=actual_output[:200] if len(actual_output) > 200 else actual_output
                )
                
        except subprocess.TimeoutExpired:
            logger.debug(f"[验证服务] {problem_id} - 测试点 {case_name}: TLE")
            return TestCaseResult(
                case_name=case_name,
                passed=False,
                reason=f"超时（>{self.config.timeout}s）"
            )
        except Exception as e:
            logger.debug(f"[验证服务] {problem_id} - 测试点 {case_name}: RE ({str(e)})")
            return TestCaseResult(
                case_name=case_name,
                passed=False,
                reason=f"运行错误: {str(e)}"
            )
    
    def _compare_output(self, expected: str, actual: str) -> bool:
        """对比输出
        
        根据配置的比较模式进行对比
        
        Args:
            expected: 期望输出
            actual: 实际输出
            
        Returns:
            是否匹配
        """
        if self.config.comparison_mode == "strict":
            return expected == actual
        
        elif self.config.comparison_mode == "ignore_trailing_spaces":
            # 分割成行并去除每行末尾空白
            expected_lines = [line.rstrip() for line in expected.split('\n')]
            actual_lines = [line.rstrip() for line in actual.split('\n')]
            
            # 移除末尾的空行
            while expected_lines and not expected_lines[-1]:
                expected_lines.pop()
            while actual_lines and not actual_lines[-1]:
                actual_lines.pop()
            
            return expected_lines == actual_lines
        
        elif self.config.comparison_mode == "ignore_all_spaces":
            # 移除所有空白字符进行比较
            expected_no_space = ''.join(expected.split())
            actual_no_space = ''.join(actual.split())
            return expected_no_space == actual_no_space
        
        else:
            # 默认使用 ignore_trailing_spaces 逻辑
            expected_lines = [line.rstrip() for line in expected.split('\n')]
            actual_lines = [line.rstrip() for line in actual.split('\n')]
            while expected_lines and not expected_lines[-1]:
                expected_lines.pop()
            while actual_lines and not actual_lines[-1]:
                actual_lines.pop()
            return expected_lines == actual_lines

