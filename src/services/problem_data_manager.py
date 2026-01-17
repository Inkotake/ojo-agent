# -*- coding: utf-8 -*-
"""题目数据管理器 - 统一管理 problem_data.json"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from loguru import logger


class ProblemDataManager:
    """题目数据管理器
    
    职责：
    - 统一管理 problem_data.json 的读写
    - 保存和读取适配器特定数据（如 HydroOJ real_id）
    - 保存图片信息
    - 数据版本管理
    """
    
    DATA_VERSION = "1.0"
    
    @staticmethod
    def _get_data_file_path(workspace_dir: Path) -> Path:
        """获取数据文件路径"""
        return workspace_dir / "problem_data.json"
    
    @staticmethod
    def load(workspace_dir: Path) -> Dict[str, Any]:
        """加载题目数据
        
        Args:
            workspace_dir: 工作区目录
            
        Returns:
            题目数据字典，不存在则返回空字典
        """
        data_file = ProblemDataManager._get_data_file_path(workspace_dir)
        
        if not data_file.exists():
            logger.debug(f"题目数据文件不存在: {data_file}")
            return {}
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"加载题目数据: {data_file}")
            return data
        except Exception as e:
            logger.error(f"加载题目数据失败: {e}")
            return {}
    
    @staticmethod
    def save(workspace_dir: Path, data: Dict[str, Any]):
        """保存题目数据
        
        Args:
            workspace_dir: 工作区目录
            data: 题目数据
        """
        data_file = ProblemDataManager._get_data_file_path(workspace_dir)
        
        # 确保目录存在
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 添加版本信息
        if "_data_version" not in data:
            data["_data_version"] = ProblemDataManager.DATA_VERSION
        
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"保存题目数据: {data_file}")
        except Exception as e:
            logger.error(f"保存题目数据失败: {e}")
    
    @staticmethod
    def update(workspace_dir: Path, updates: Dict[str, Any]):
        """更新题目数据（部分更新）
        
        Args:
            workspace_dir: 工作区目录
            updates: 要更新的数据
        """
        data = ProblemDataManager.load(workspace_dir)
        data.update(updates)
        ProblemDataManager.save(workspace_dir, data)
    
    # ========== 上传适配器 real_id（通用） ==========
    
    @staticmethod
    def set_upload_real_id(workspace_dir: Path, adapter_name: str, real_id: str):
        """保存上传适配器的 real_id
        
        Args:
            workspace_dir: 工作区目录
            adapter_name: 适配器名称（如 hydrooj, shsoj）
            real_id: 上传后的真实题目 ID
        """
        data = ProblemDataManager.load(workspace_dir)
        upload_ids = data.get("upload_real_ids", {})
        upload_ids[adapter_name] = real_id
        ProblemDataManager.update(workspace_dir, {"upload_real_ids": upload_ids})
        logger.debug(f"保存 {adapter_name} real_id: {real_id}")
    
    @staticmethod
    def get_upload_real_id(workspace_dir: Path, adapter_name: str) -> Optional[str]:
        """读取上传适配器的 real_id
        
        Args:
            workspace_dir: 工作区目录
            adapter_name: 适配器名称
            
        Returns:
            上传后的真实题目 ID，不存在则返回 None
        """
        data = ProblemDataManager.load(workspace_dir)
        upload_ids = data.get("upload_real_ids", {})
        return upload_ids.get(adapter_name)
    
    # ========== HydroOJ 特定数据（向后兼容） ==========
    
    @staticmethod
    def set_hydrooj_real_id(workspace_dir: Path, real_id: str):
        """保存 HydroOJ real_id（向后兼容，内部调用通用方法）"""
        ProblemDataManager.set_upload_real_id(workspace_dir, "hydrooj", real_id)
    
    @staticmethod
    def get_hydrooj_real_id(workspace_dir: Path) -> Optional[str]:
        """读取 HydroOJ real_id（向后兼容，内部调用通用方法）"""
        return ProblemDataManager.get_upload_real_id(workspace_dir, "hydrooj")
    
    # ========== 图片信息 ==========
    
    @staticmethod
    def set_images(workspace_dir: Path, images: List[Dict[str, Any]]):
        """保存图片信息
        
        Args:
            workspace_dir: 工作区目录
            images: 图片信息列表
        """
        ProblemDataManager.update(workspace_dir, {"images": images})
        logger.debug(f"保存 {len(images)} 张图片信息")
    
    @staticmethod
    def get_images(workspace_dir: Path) -> List[Dict[str, Any]]:
        """读取图片信息
        
        Args:
            workspace_dir: 工作区目录
            
        Returns:
            图片信息列表
        """
        data = ProblemDataManager.load(workspace_dir)
        return data.get("images", [])
    
    # ========== 验证信息 ==========
    
    @staticmethod
    def set_validation_result(workspace_dir: Path, validation_data: Dict[str, Any]):
        """保存验证结果
        
        Args:
            workspace_dir: 工作区目录
            validation_data: 验证数据
        """
        ProblemDataManager.update(workspace_dir, {"validation": validation_data})
        logger.debug(f"保存验证结果")
    
    @staticmethod
    def get_validation_result(workspace_dir: Path) -> Optional[Dict[str, Any]]:
        """读取验证结果
        
        Args:
            workspace_dir: 工作区目录
            
        Returns:
            验证结果，不存在则返回 None
        """
        data = ProblemDataManager.load(workspace_dir)
        return data.get("validation")
    
    # ========== 适配器特定数据 ==========
    
    @staticmethod
    def set_adapter_data(workspace_dir: Path, adapter_name: str, adapter_data: Dict[str, Any]):
        """保存适配器特定数据
        
        Args:
            workspace_dir: 工作区目录
            adapter_name: 适配器名称
            adapter_data: 适配器数据
        """
        data = ProblemDataManager.load(workspace_dir)
        
        if "_adapter_data" not in data:
            data["_adapter_data"] = {}
        
        data["_adapter_data"][adapter_name] = adapter_data
        ProblemDataManager.save(workspace_dir, data)
        logger.debug(f"保存适配器数据: {adapter_name}")
    
    @staticmethod
    def get_adapter_data(workspace_dir: Path, adapter_name: str) -> Optional[Dict[str, Any]]:
        """读取适配器特定数据
        
        Args:
            workspace_dir: 工作区目录
            adapter_name: 适配器名称
            
        Returns:
            适配器数据，不存在则返回 None
        """
        data = ProblemDataManager.load(workspace_dir)
        adapter_data = data.get("_adapter_data", {})
        return adapter_data.get(adapter_name)
    
    # ========== 处理状态跟踪 ==========
    
    @staticmethod
    def set_processing_status(workspace_dir: Path, status: Dict[str, Any]):
        """保存处理状态
        
        Args:
            workspace_dir: 工作区目录
            status: 状态数据，包含:
                - stage: 当前阶段 (fetch/gen/upload/solve/completed)
                - ok_gen: 生成是否成功
                - ok_upload: 上传是否成功
                - ok_solve: 求解是否成功
                - last_error: 最后错误信息
                - attempts: 尝试次数
                - completed_at: 完成时间
        """
        data = ProblemDataManager.load(workspace_dir)
        if "_processing" not in data:
            data["_processing"] = {}
        data["_processing"].update(status)
        data["_processing"]["updated_at"] = datetime.now().isoformat()
        ProblemDataManager.save(workspace_dir, data)
    
    @staticmethod
    def get_processing_status(workspace_dir: Path) -> Optional[Dict[str, Any]]:
        """获取处理状态"""
        data = ProblemDataManager.load(workspace_dir)
        return data.get("_processing")
    
    @staticmethod
    def is_completed(workspace_dir: Path) -> bool:
        """检查是否已完成（AC通过）"""
        status = ProblemDataManager.get_processing_status(workspace_dir)
        if not status:
            return False
        return status.get("ok_solve", False) or status.get("stage") == "completed"
    
    @staticmethod
    def mark_completed(workspace_dir: Path, solve_result: bool = True):
        """标记为已完成"""
        from datetime import datetime
        ProblemDataManager.set_processing_status(workspace_dir, {
            "stage": "completed",
            "ok_solve": solve_result,
            "completed_at": datetime.now().isoformat()
        })
    
    # ========== 实用方法 ==========
    
    @staticmethod
    def exists(workspace_dir: Path) -> bool:
        """检查数据文件是否存在
        
        Args:
            workspace_dir: 工作区目录
            
        Returns:
            是否存在
        """
        return ProblemDataManager._get_data_file_path(workspace_dir).exists()
    
    @staticmethod
    def get_title(workspace_dir: Path) -> Optional[str]:
        """获取题目标题
        
        Args:
            workspace_dir: 工作区目录
            
        Returns:
            题目标题
        """
        data = ProblemDataManager.load(workspace_dir)
        return data.get("title")
    
    @staticmethod
    def get_tags(workspace_dir: Path) -> List[str]:
        """获取题目标签
        
        Args:
            workspace_dir: 工作区目录
            
        Returns:
            标签列表
        """
        data = ProblemDataManager.load(workspace_dir)
        tags = data.get("tags", [])
        return tags if isinstance(tags, list) else []

