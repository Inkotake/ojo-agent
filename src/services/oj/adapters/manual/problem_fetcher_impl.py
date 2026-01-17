# -*- coding: utf-8 -*-
"""Manual题面获取实现"""

from typing import Dict, Any, Optional
from pathlib import Path
import json

from loguru import logger

from ...base.problem_fetcher import ProblemFetcher


class ManualProblemFetcher(ProblemFetcher):
    """手动题面获取器"""
    
    def __init__(self, workspace_dir: Path = None):
        # workspace_dir 应该是用户隔离的工作区 (如 workspace/user_1)
        if workspace_dir:
            self.workspace_dir = workspace_dir
        else:
            # 支持环境变量
            import os
            workspace_base = os.getenv("OJO_WORKSPACE")
            if not workspace_base:
                docker_workspace = Path("/app/workspace")
                if docker_workspace.exists():
                    workspace_base = str(docker_workspace)
                else:
                    workspace_base = "workspace"
            self.workspace_dir = Path(workspace_base)
        self.temp_dir = self.workspace_dir / ".manual_temp"
    
    def supports_url(self, url: str) -> bool:
        """判断是否支持该URL（manual://协议）"""
        return url.startswith("manual://")
    
    def parse_problem_id(self, input_str: str) -> Optional[str]:
        """从URL中解析题目ID
        
        格式: manual://<canonical_id>
        示例: manual://manual_矩阵乘法_20250101120000 或 manual://manual_temp_20250101120000
        """
        if not input_str.startswith("manual://"):
            return None
        
        # 提取manual后面的部分
        problem_id = input_str[9:]  # 去掉 "manual://" 前缀
        return problem_id if problem_id else None
    
    def fetch_problem(self, problem_id: str) -> Dict[str, Any]:
        """获取题目数据（自动处理临时文件和已格式化文件）
        
        Args:
            problem_id: 题目ID（如 manual_temp_xxx 或 manual_xxx）
            
        Returns:
            标准格式的题目数据
            
        Raises:
            FileNotFoundError: 题面文件不存在
            RuntimeError: 读取或格式化失败
        """
        # 检查是否为临时文件（需要格式化）
        if problem_id.startswith("manual_temp_"):
            return self._format_and_save(problem_id)
        
        # 否则读取已格式化的文件
        problem_dir = self.workspace_dir / f"problem_{problem_id}"
        problem_data_file = problem_dir / "problem_data.json"
        
        if not problem_data_file.exists():
            raise FileNotFoundError(f"题面文件不存在: {problem_data_file}")
        
        try:
            with open(problem_data_file, 'r', encoding='utf-8') as f:
                problem_data = json.load(f)
            
            logger.info(f"[{problem_id}] 成功读取题面数据")
            return problem_data
            
        except json.JSONDecodeError as e:
            raise RuntimeError(f"解析题面JSON失败: {e}")
        except Exception as e:
            raise RuntimeError(f"读取题面失败: {e}")
    
    def _format_and_save(self, temp_id: str) -> Dict[str, Any]:
        """格式化临时题面并保存到工作区
        
        Args:
            temp_id: 临时ID（如 manual_temp_20250101120000）
            
        Returns:
            格式化后的题目数据
        """
        # 读取原始题面文本
        temp_file = self.temp_dir / f"{temp_id}.txt"
        if not temp_file.exists():
            raise FileNotFoundError(f"临时题面文件不存在: {temp_file}")
        
        try:
            with open(temp_file, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            
            logger.info(f"[{temp_id}] 开始格式化题面...")
            
            # 导入格式化器（延迟导入避免循环依赖）
            from services.manual_problem_formatter import ManualProblemFormatter
            from services.unified_config import get_config
            from services.llm.factory import LLMFactory
            
            # 加载配置
            cfg = get_config()
            formatter = ManualProblemFormatter(cfg, LLMFactory(cfg))
            
            # 格式化题面
            problem_data = formatter.format_problem(raw_text)
            
            # 添加元数据（使用temp_id，保持与目录一致）
            problem_data["source"] = "manual"
            problem_data["id"] = temp_id
            problem_data["url"] = f"manual://{temp_id}"
            
            logger.info(f"[{temp_id}] 格式化成功，标题: {problem_data.get('title', '未命名')}")
            
            # 保存到工作区（确保后续步骤能访问）
            problem_dir = self.workspace_dir / f"problem_{temp_id}"
            problem_dir.mkdir(parents=True, exist_ok=True)
            problem_data_file = problem_dir / "problem_data.json"
            
            try:
                with open(problem_data_file, 'w', encoding='utf-8') as f:
                    json.dump(problem_data, f, ensure_ascii=False, indent=2)
                logger.debug(f"[{temp_id}] 已保存题面数据到: {problem_data_file}")
            except Exception as e:
                logger.warning(f"[{temp_id}] 保存题面数据失败: {e}")
            
            # 删除临时文件
            try:
                temp_file.unlink()
            except Exception:
                pass
            
            return problem_data
            
        except Exception as e:
            logger.error(f"[{temp_id}] 格式化失败: {e}")
            raise RuntimeError(f"格式化题面失败: {e}")

