# -*- coding: utf-8 -*-
"""SHSOJ批量适配器实现 - 按标签批量获取题目"""

import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QListWidget, QSpinBox, QMessageBox, QListWidgetItem
)
from PySide6.QtCore import Qt

from loguru import logger

from ...base.batch_adapter import BatchAdapter


class SHSOJBatchAdapter(BatchAdapter):
    """SHSOJ批量适配器 - 按标签批量获取题目
    
    基于api-tcoj.aicoders.cn的API实现标签查询和批量获取
    """
    
    def __init__(self, base_url: str = "", timeout: int = 15):
        """初始化SHSOJ批量适配器
        
        Args:
            base_url: API基础URL，默认为空时使用api-tcoj.aicoders.cn
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/") if base_url else "https://api-tcoj.aicoders.cn"
        self.timeout = timeout
        self.session = self._make_session()
        self._tag_cache: Optional[Dict[int, Dict[str, Any]]] = None
        self._tag_cache_names: Optional[List[str]] = None
        
        # GUI控件（在create_input_widget时创建）
        self.tag_input: Optional[QLineEdit] = None
        self.tag_list: Optional[QListWidget] = None
        self.keyword_input: Optional[QLineEdit] = None
        self.page_size_spin: Optional[QSpinBox] = None
        self.btn_refresh_tags: Optional[QPushButton] = None
        self.btn_batch_select: Optional[QPushButton] = None
    
    @property
    def name(self) -> str:
        return "shsoj_batch_tag"
    
    @property
    def display_name(self) -> str:
        return "SHSOJ - 按标签批量获取"
    
    def _make_session(self) -> requests.Session:
        """创建请求会话（带重试机制）"""
        s = requests.Session()
        retries = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"])
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=utf-8",
            "Origin": "https://oj.aicoders.cn",
            "Referer": "https://oj.aicoders.cn/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/141.0.0.0 Safari/537.36"
            ),
            "url-type": "general",
        }
        s.headers.update(headers)
        return s
    
    def api_get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送GET请求
        
        Args:
            path: API路径
            params: 查询参数
            
        Returns:
            响应数据
        """
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        
        # 检查API返回状态
        if not isinstance(data, dict) or data.get("status") != 200:
            raise RuntimeError(f"API返回非200状态: {url} params={params} resp={data}")
        
        return data
    
    def _load_all_tags(self, force_refresh: bool = False) -> Dict[int, Dict[str, Any]]:
        """加载所有标签分组
        
        Args:
            force_refresh: 强制刷新缓存
            
        Returns:
            标签ID到标签对象的映射
        """
        if self._tag_cache is not None and not force_refresh:
            return self._tag_cache
        
        logger.info("加载标签列表...")
        data = self.api_get("/api/get-problem-tags-group", {
            "type": 0,
            "publishStatus": 1
        })
        
        tag_map: Dict[int, Dict[str, Any]] = {}
        groups = data.get("data") or []
        
        for g in groups:
            clist = (g or {}).get("classificationList") or []
            for c in clist:
                for t in (c.get("tagList") or []):
                    tid = int(t["id"])
                    tag_map[tid] = t
        
        if not tag_map:
            raise RuntimeError("未获取到任何标签，可能接口变化或网络异常")
        
        self._tag_cache = tag_map
        self._tag_cache_names = sorted([t.get("name", "") for t in tag_map.values()], 
                                       key=lambda x: x.lower())
        
        logger.info(f"加载了 {len(tag_map)} 个标签")
        return tag_map
    
    def _resolve_tag_id(self, tag_map: Dict[int, Dict[str, Any]], 
                       tag_name: str) -> int:
        """解析标签名到标签ID
        
        Args:
            tag_map: 标签映射
            tag_name: 标签名
            
        Returns:
            标签ID
            
        Raises:
            KeyError: 未找到标签
        """
        # 精确匹配
        matches = [tid for tid, t in tag_map.items() 
                  if t.get("name") == tag_name]
        
        if not matches:
            # 大小写/空格宽松匹配
            norm = tag_name.strip().lower()
            matches = [tid for tid, t in tag_map.items() 
                      if str(t.get("name", "")).strip().lower() == norm]
        
        if not matches:
            raise KeyError(f"未找到标签名：{tag_name}")
        
        if len(matches) > 1:
            logger.warning(f"标签名'{tag_name}'存在多条同名记录，将取第一条。ID：{matches}")
        
        return matches[0]
    
    def _fetch_all_problem_ids_by_tag(self, tag_id: int, page_size: int = 30, 
                                     sleep_sec: float = 0.2) -> List[Dict[str, Any]]:
        """分页获取指定标签下的所有题目
        
        Args:
            tag_id: 标签ID
            page_size: 每页大小
            sleep_sec: 请求间隔（秒）
            
        Returns:
            题目记录列表
        """
        current = 1
        all_records: List[Dict[str, Any]] = []
        
        while True:
            payload = {
                "onlyFinish": 1,
                "sort": "gmt_create",
                "order": "desc",
                "currentPage": current,
                "limit": page_size,
                "tagId": tag_id,
            }
            
            data = self.api_get("/api/get-problem-list", payload).get("data") or {}
            records = data.get("records") or []
            total_pages = int(data.get("pages") or 0)
            
            if not records:
                break
            
            all_records.extend(records)
            logger.debug(f"第 {current}/{max(total_pages, current)} 页，累计 {len(all_records)} 题")
            
            if total_pages and current >= total_pages:
                break
            
            current += 1
            time.sleep(sleep_sec)
        
        return all_records
    
    def create_input_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        """创建输入界面"""
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        # 标签输入行
        tag_layout = QHBoxLayout()
        tag_layout.addWidget(QLabel("标签名:"))
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("例如: 双重循环 或 双重循环,字典树,动态规划")
        self.tag_input.setToolTip("输入标签名称（支持多个，用逗号或分号分隔），例如：双重循环,字典树")
        tag_layout.addWidget(self.tag_input)
        
        # 刷新标签按钮
        self.btn_refresh_tags = QPushButton("刷新标签")
        self.btn_refresh_tags.clicked.connect(lambda: self._refresh_tags(widget))
        tag_layout.addWidget(self.btn_refresh_tags)
        
        layout.addLayout(tag_layout)
        
        # 关键词批量选择行
        keyword_layout = QHBoxLayout()
        keyword_layout.addWidget(QLabel("关键词批量选择:"))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("输入关键词，例如: 循环 或 树,动态")
        self.keyword_input.setToolTip("输入关键词（支持多个，用逗号或分号分隔），将自动选中包含关键词的标签")
        keyword_layout.addWidget(self.keyword_input)
        
        self.btn_batch_select = QPushButton("批量选择")
        self.btn_batch_select.clicked.connect(lambda: self._batch_select_by_keywords(widget))
        keyword_layout.addWidget(self.btn_batch_select)
        
        layout.addLayout(keyword_layout)
        
        # 标签列表（用于显示可用标签，支持多选）
        list_label_layout = QHBoxLayout()
        list_label_layout.addWidget(QLabel("可用标签列表（支持多选，点击选择）:"))
        btn_clear_selection = QPushButton("清除选择")
        btn_clear_selection.clicked.connect(self._clear_selection)
        list_label_layout.addWidget(btn_clear_selection)
        list_label_layout.addStretch()
        layout.addLayout(list_label_layout)
        
        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(150)
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        # 点击标签时，添加到输入框（支持多个）
        self.tag_list.itemClicked.connect(self._on_tag_item_clicked)
        layout.addWidget(self.tag_list)
        
        # 分页选项
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("每页数量:"))
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(10, 100)
        self.page_size_spin.setValue(30)
        self.page_size_spin.setToolTip("API每页返回的题目数量")
        options_layout.addWidget(self.page_size_spin)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # 自动加载标签列表
        self._refresh_tags(widget)
        
        return widget
    
    def _refresh_tags(self, parent_widget: QWidget):
        """刷新标签列表"""
        try:
            self._load_all_tags(force_refresh=True)
            if self.tag_list and self._tag_cache_names:
                self.tag_list.clear()
                for name in self._tag_cache_names:
                    self.tag_list.addItem(name)
        except Exception as e:
            logger.exception(e)
            QMessageBox.warning(parent_widget, "加载失败", 
                              f"无法加载标签列表：{e}")
    
    def _on_tag_item_clicked(self, item: QListWidgetItem):
        """标签项点击事件：将选中的标签添加到输入框"""
        selected_items = self.tag_list.selectedItems()
        if selected_items:
            selected_tags = [item.text() for item in selected_items]
            self.tag_input.setText(", ".join(selected_tags))
    
    def _clear_selection(self):
        """清除标签列表的选择"""
        if self.tag_list:
            self.tag_list.clearSelection()
            self.tag_input.clear()
    
    def _batch_select_by_keywords(self, parent_widget: QWidget):
        """根据关键词批量选择标签"""
        if not self.keyword_input or not self.tag_list:
            return
        
        keywords_text = self.keyword_input.text().strip()
        if not keywords_text:
            QMessageBox.information(parent_widget, "提示", "请输入关键词")
            return
        
        # 解析关键词（支持逗号、分号、空格分隔）
        keywords = re.split(r'[,;\s]+', keywords_text)
        keywords = [k.strip().lower() for k in keywords if k.strip()]
        
        if not keywords:
            QMessageBox.information(parent_widget, "提示", "请输入有效的关键词")
            return
        
        # 匹配标签
        matched_count = 0
        self.tag_list.clearSelection()
        
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            tag_name = item.text().lower()
            
            # 检查标签名是否包含任一关键词
            for keyword in keywords:
                if keyword in tag_name:
                    item.setSelected(True)
                    matched_count += 1
                    break
        
        if matched_count > 0:
            # 更新输入框
            selected_items = self.tag_list.selectedItems()
            selected_tags = [item.text() for item in selected_items]
            self.tag_input.setText(", ".join(selected_tags))
            QMessageBox.information(
                parent_widget, "批量选择完成", 
                f"已选中 {matched_count} 个匹配的标签"
            )
        else:
            QMessageBox.information(parent_widget, "无匹配", "没有找到匹配的标签")
    
    def validate_input(self, input_data: Dict[str, Any]) -> tuple[bool, str]:
        """验证输入数据"""
        tag_names_str = input_data.get("tag_name", "").strip()
        
        if not tag_names_str:
            return False, "标签名不能为空"
        
        # 解析多个标签名（支持逗号、分号分隔）
        import re
        tag_names = re.split(r'[,;]+', tag_names_str)
        tag_names = [name.strip() for name in tag_names if name.strip()]
        
        if not tag_names:
            return False, "标签名不能为空"
        
        # 检查所有标签是否存在
        try:
            tag_map = self._load_all_tags()
            for tag_name in tag_names:
                self._resolve_tag_id(tag_map, tag_name)
        except KeyError as e:
            return False, str(e)
        except Exception as e:
            return False, f"加载标签失败：{e}"
        
        return True, ""
    
    def fetch_problem_urls(self, input_data: Dict[str, Any]) -> List[str]:
        """按标签批量获取题目URL（支持多个标签）"""
        tag_names_str = input_data.get("tag_name", "").strip()
        page_size = input_data.get("page_size", 30)
        
        # 解析多个标签名（支持逗号、分号分隔）
        import re
        tag_names = re.split(r'[,;]+', tag_names_str)
        tag_names = [name.strip() for name in tag_names if name.strip()]
        
        if not tag_names:
            logger.warning("标签名不能为空")
            return []
        
        logger.info(f"开始获取 {len(tag_names)} 个标签下的题目: {tag_names}")
        
        # 1. 加载标签映射
        tag_map = self._load_all_tags()
        
        # 2. 解析所有tag_id
        tag_ids = []
        for tag_name in tag_names:
            try:
                tag_id = self._resolve_tag_id(tag_map, tag_name)
                tag_info = tag_map[tag_id]
                tag_ids.append((tag_id, tag_info.get('name', tag_name)))
                logger.info(f"标签: {tag_info.get('name')} (ID={tag_id})")
            except KeyError as e:
                logger.warning(f"跳过无效标签 '{tag_name}': {e}")
                continue
        
        if not tag_ids:
            logger.warning("没有有效的标签")
            return []
        
        # 3. 分页获取所有标签下的题目列表（合并去重）
        all_problem_ids = set()  # 使用set去重
        all_records = []  # 保留完整记录用于日志
        
        for tag_id, tag_name in tag_ids:
            logger.info(f"正在获取标签 '{tag_name}' (ID={tag_id}) 下的题目...")
            records = self._fetch_all_problem_ids_by_tag(tag_id, page_size)
            
            for r in records:
                # 从API响应中读取题号，使用 problemId 字段（非编辑/更新场景）
                problem_id = r.get("problemId")
                if problem_id is None:
                    logger.warning(f"记录中缺少 problemId 字段，跳过记录: {r}")
                    continue
                
                pid = str(problem_id)
                if pid not in all_problem_ids:
                    all_problem_ids.add(pid)
                    all_records.append(r)
            
            logger.info(f"标签 '{tag_name}' 下获取到 {len(records)} 道题目")
        
        if not all_records:
            logger.warning(f"所有标签下未发现题目")
            return []
        
        # 4. 读取 finished.txt，获取已完成的题目列表
        finished_problems = set()
        finish_file = Path("finished.txt")
        if finish_file.exists():
            try:
                with open(finish_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # 解析格式：timestamp | url | AC
                        parts = line.split('|')
                        if len(parts) >= 2:
                            problem_url = parts[1].strip()
                            finished_problems.add(problem_url)
                logger.info(f"已读取 finished.txt，共 {len(finished_problems)} 个已完成题目")
            except Exception as e:
                logger.warning(f"读取 finished.txt 失败: {e}")
        
        # 5. 生成URL列表，过滤掉已完成的题目
        urls = []
        skipped_count = 0
        for r in all_records:
            # 从API响应中读取题号，使用 problemId 字段（非编辑/更新场景）
            problem_id = r.get("problemId")
            if problem_id is None:
                logger.warning(f"记录中缺少 problemId 字段，跳过记录: {r}")
                continue
            
            pid = str(problem_id)
            url = f"https://oj.aicoders.cn/problem/{pid}"
            
            # 检查是否已在 finished.txt 中
            if url in finished_problems:
                skipped_count += 1
                logger.debug(f"跳过已完成题目: {url}")
                continue
            
            urls.append(url)
            logger.debug(f"生成URL: {url} (题号: {pid})")
        
        if skipped_count > 0:
            logger.info(f"跳过 {skipped_count} 个已完成题目（已在 finished.txt 中）")
        
        logger.info(f"成功获取 {len(urls)} 道题目（已去重，已过滤已完成）")
        return urls
    
    def read_finished_problems(self, finished_file: str = "finished.txt") -> List[str]:
        """读取finished.txt中的题目URL列表
        
        Args:
            finished_file: finished.txt文件路径
            
        Returns:
            题目URL列表
        """
        from pathlib import Path
        
        finished_path = Path(finished_file)
        if not finished_path.exists():
            logger.warning(f"finished.txt文件不存在: {finished_path}")
            return []
        
        urls = []
        with open(finished_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 解析格式: 时间 | URL | AC
                parts = line.split('|')
                if len(parts) >= 2:
                    url = parts[1].strip()
                    if url and url.startswith('http'):
                        urls.append(url)
        
        logger.info(f"从finished.txt读取到 {len(urls)} 个题目URL")
        return urls
    
    def upload_finished_problems(self, finished_file: str = "finished.txt", 
                                 workspace_dir: str = "workspace",
                                 log_callback=None) -> Dict[str, Any]:
        """读取finished.txt中的题目并调用适配器上传（已废弃，建议使用read_finished_problems + pipeline）
        
        Args:
            finished_file: finished.txt文件路径
            workspace_dir: workspace目录路径
            log_callback: 日志回调函数
            
        Returns:
            上传结果统计
        """
        from pathlib import Path
        import re
        from services.oj.registry import get_global_registry
        from services.unified_config import ConfigManager
        
        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            logger.info(msg)
        
        finished_path = Path(finished_file)
        if not finished_path.exists():
            error_msg = f"finished.txt文件不存在: {finished_path}"
            _log(error_msg)
            return {"success": False, "error": error_msg, "total": 0, "uploaded": 0, "failed": 0}
        
        workspace_path = Path(workspace_dir)
        if not workspace_path.exists():
            error_msg = f"workspace目录不存在: {workspace_path}"
            _log(error_msg)
            return {"success": False, "error": error_msg, "total": 0, "uploaded": 0, "failed": 0}
        
        # 读取finished.txt
        _log(f"读取finished.txt: {finished_path}")
        urls = []
        with open(finished_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 解析格式: 时间 | URL | AC
                parts = line.split('|')
                if len(parts) >= 2:
                    url = parts[1].strip()
                    if url and url.startswith('http'):
                        urls.append(url)
        
        if not urls:
            _log("finished.txt中没有找到有效的URL")
            return {"success": True, "total": 0, "uploaded": 0, "failed": 0, "skipped": 0}
        
        _log(f"找到 {len(urls)} 个题目URL")
        
        # 获取适配器注册表
        registry = get_global_registry()
        
        # 获取配置并登录
        from services.unified_config import get_config
        cfg = get_config()
        
        # 获取SHSOJ适配器
        adapter = registry.get_adapter("shsoj")
        if not adapter:
            # 尝试创建适配器
            from .adapter import SHSOJAdapter
            adapter = SHSOJAdapter()
            registry.register(adapter)
        
        # 登录获取认证
        _log("正在登录获取认证...")
        try:
            auth = adapter.login()
            _log("登录成功")
        except Exception as e:
            error_msg = f"登录失败: {e}"
            _log(error_msg)
            return {"success": False, "error": error_msg, "total": len(urls), "uploaded": 0, "failed": 0}
        
        # 统计结果
        results = {
            "success": True,
            "total": len(urls),
            "uploaded": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }
        
        # 处理每个URL
        for idx, url in enumerate(urls, 1):
            _log(f"[{idx}/{len(urls)}] 处理: {url}")
            
            # 从URL提取题目ID
            problem_id = None
            match = re.search(r'/problem/(\d+)', url)
            if match:
                problem_id = match.group(1)
            else:
                _log(f"  无法从URL提取题目ID，跳过: {url}")
                results["skipped"] += 1
                results["details"].append({"url": url, "status": "skipped", "reason": "无法提取题目ID"})
                continue
            
            # 查找zip文件
            problem_dir = workspace_path / f"problem_aicoders_{problem_id}"
            if not problem_dir.exists():
                _log(f"  题目目录不存在，跳过: {problem_dir}")
                results["skipped"] += 1
                results["details"].append({"url": url, "problem_id": problem_id, "status": "skipped", "reason": "目录不存在"})
                continue
            
            # 查找zip文件（优先查找标准格式）
            zip_files = list(problem_dir.glob(f"problem_aicoders_{problem_id}_testcase.zip"))
            if not zip_files:
                # 尝试其他格式
                zip_files = list(problem_dir.glob(f"problem_*{problem_id}*testcase.zip"))
            
            if not zip_files:
                _log(f"  未找到zip文件，跳过: {problem_dir}")
                results["skipped"] += 1
                results["details"].append({"url": url, "problem_id": problem_id, "status": "skipped", "reason": "未找到zip文件"})
                continue
            
            zip_path = zip_files[0]  # 使用第一个找到的zip文件
            _log(f"  找到zip文件: {zip_path.name}")
            
            # 调用适配器上传
            try:
                _log(f"  开始上传题目 {problem_id}...")
                upload_result = adapter.upload_and_update_problem(
                    auth=auth,
                    original_id=problem_id,
                    zip_path=str(zip_path),
                    log_callback=lambda pid, msg: _log(f"    [{pid}] {msg}")
                )
                
                if upload_result and upload_result.get("success"):
                    _log(f"  ✓ 上传成功: {problem_id}")
                    results["uploaded"] += 1
                    results["details"].append({
                        "url": url,
                        "problem_id": problem_id,
                        "status": "success",
                        "result": upload_result
                    })
                else:
                    error_msg = upload_result.get("error", "未知错误") if upload_result else "返回结果为空"
                    _log(f"  ✗ 上传失败: {problem_id} - {error_msg}")
                    results["failed"] += 1
                    results["details"].append({
                        "url": url,
                        "problem_id": problem_id,
                        "status": "failed",
                        "error": error_msg
                    })
            except Exception as e:
                error_msg = str(e)
                _log(f"  ✗ 上传异常: {problem_id} - {error_msg}")
                logger.exception(e)
                results["failed"] += 1
                results["details"].append({
                    "url": url,
                    "problem_id": problem_id,
                    "status": "failed",
                    "error": error_msg
                })
        
        # 输出统计
        _log(f"\n上传完成统计:")
        _log(f"  总计: {results['total']}")
        _log(f"  成功: {results['uploaded']}")
        _log(f"  失败: {results['failed']}")
        _log(f"  跳过: {results['skipped']}")
        
        return results

