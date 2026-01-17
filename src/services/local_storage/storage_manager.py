# -*- coding: utf-8 -*-
"""本地题目存储管理器"""

from pathlib import Path
from typing import Optional, List
from loguru import logger

from .problem_schema import ProblemMetadata


class LocalStorageManager:
    """本地题目存储管理
    
    负责将题目数据保存到本地文件系统，并支持加载
    """
    
    def __init__(self, workspace: Path):
        """初始化存储管理器
        
        Args:
            workspace: 工作空间根目录
        """
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
    
    def get_problem_dir(self, source: str, problem_id: str) -> Path:
        """获取题目目录路径
        
        Args:
            source: 来源OJ
            problem_id: 题目ID
            
        Returns:
            题目目录路径
        """
        return self.workspace / f"problem_{source}_{problem_id}"
    
    def save_problem(self, problem: ProblemMetadata) -> Path:
        """保存题目到本地（JSON格式）
        
        Args:
            problem: 题目元数据
            
        Returns:
            保存的目录路径
        """
        problem_dir = self.get_problem_dir(problem.source, problem.id)
        problem_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存元数据
        metadata_file = problem_dir / "problem.json"
        metadata_file.write_text(problem.to_json(), encoding='utf-8')
        
        logger.info(f"题目已保存: {problem.source}/{problem.id} -> {problem_dir}")
        return problem_dir
    
    def load_problem(self, source: str, problem_id: str) -> Optional[ProblemMetadata]:
        """从本地加载题目
        
        Args:
            source: 来源OJ
            problem_id: 题目ID
            
        Returns:
            题目元数据，不存在返回None
        """
        problem_dir = self.get_problem_dir(source, problem_id)
        metadata_file = problem_dir / "problem.json"
        
        if not metadata_file.exists():
            logger.warning(f"题目不存在: {source}/{problem_id}")
            return None
        
        try:
            problem = ProblemMetadata.from_json(metadata_file.read_text(encoding='utf-8'))
            logger.debug(f"题目已加载: {source}/{problem_id}")
            return problem
        except Exception as e:
            logger.error(f"加载题目失败: {source}/{problem_id}, 错误: {e}")
            return None
    
    def problem_exists(self, source: str, problem_id: str) -> bool:
        """检查题目是否存在
        
        Args:
            source: 来源OJ
            problem_id: 题目ID
            
        Returns:
            是否存在
        """
        problem_dir = self.get_problem_dir(source, problem_id)
        metadata_file = problem_dir / "problem.json"
        return metadata_file.exists()
    
    def list_problems(self, source: Optional[str] = None) -> List[tuple[str, str]]:
        """列出所有本地题目
        
        Args:
            source: 如果指定，只列出该来源的题目
            
        Returns:
            (source, problem_id) 元组列表
        """
        problems = []
        
        for dir_path in self.workspace.iterdir():
            if not dir_path.is_dir():
                continue
            
            # 解析目录名：problem_{source}_{id}
            dir_name = dir_path.name
            if not dir_name.startswith("problem_"):
                continue
            
            parts = dir_name[8:].split("_", 1)  # 去掉"problem_"前缀
            if len(parts) != 2:
                continue
            
            prob_source, prob_id = parts
            
            # 过滤来源
            if source and prob_source != source:
                continue
            
            # 检查是否有problem.json
            if (dir_path / "problem.json").exists():
                problems.append((prob_source, prob_id))
        
        return problems
    
    def delete_problem(self, source: str, problem_id: str) -> bool:
        """删除题目
        
        Args:
            source: 来源OJ
            problem_id: 题目ID
            
        Returns:
            是否成功删除
        """
        problem_dir = self.get_problem_dir(source, problem_id)
        
        if not problem_dir.exists():
            logger.warning(f"题目不存在，无法删除: {source}/{problem_id}")
            return False
        
        try:
            import shutil
            shutil.rmtree(problem_dir)
            logger.info(f"题目已删除: {source}/{problem_id}")
            return True
        except Exception as e:
            logger.error(f"删除题目失败: {source}/{problem_id}, 错误: {e}")
            return False

