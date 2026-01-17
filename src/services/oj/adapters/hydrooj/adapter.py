# -*- coding: utf-8 -*-
"""HydroOJ适配器"""

from typing import Set, Dict, Any
from pathlib import Path

from ...base import OJAdapter, OJCapability, DataUploader, SolutionSubmitter


class HydroOJAdapter(OJAdapter):
    """HydroOJ适配器（v7.0重构版）
    
    支持上传数据到HydroOJ（使用Cookie认证）
    """
    
    def __init__(self, base_url: str = "", domain: str = "", cookie: str = "", 
                 preferred_prefix: str = ""):
        # 调用基类__init__
        super().__init__()
        
        # 清理base_url，确保不包含 /d/domain 部分和首尾空格
        import re
        base_url_clean = base_url.strip().rstrip("/") if base_url else ""
        # 如果base_url包含 /d/xxx 部分，移除它
        base_url_clean = re.sub(r'/d/[^/]+/?$', '', base_url_clean).rstrip("/")
        self.base_url = base_url_clean
        self.domain = domain
        self.cookie = cookie
        self.preferred_prefix = preferred_prefix
        self._data_uploader = None
        self._solution_submitter = None
        self._config_loaded = bool(self.base_url and self.domain)
    
    def _do_initialize(self, context: Dict[str, Any]) -> bool:
        """HydroOJ特定初始化"""
        try:
            self._ensure_config()
            from loguru import logger
            logger.info(f"HydroOJ适配器配置加载成功: {self.base_url}/d/{self.domain}")
            return True
        except Exception as e:
            from loguru import logger
            logger.error(f"HydroOJ适配器配置加载失败: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        base_health = super().health_check()
        base_health["config_loaded"] = self._config_loaded
        base_health["base_url"] = self.base_url
        base_health["domain"] = self.domain
        base_health["has_cookie"] = bool(self.cookie)
        return base_health
    
    @property
    def name(self) -> str:
        return "hydrooj"
    
    @property
    def display_name(self) -> str:
        return "HydroOJ"
    
    @property
    def capabilities(self) -> Set[OJCapability]:
        return {OJCapability.UPLOAD_DATA, OJCapability.SUBMIT_SOLUTION}
    
    def _get_user_config(self, user_id: int) -> Dict[str, Any]:
        """获取用户的适配器配置（严格用户隔离）
        
        Args:
            user_id: 用户ID（必需）
        
        Returns:
            用户配置字典
        
        Raises:
            RuntimeError: 用户未配置
        """
        from core.database import get_database
        from loguru import logger
        
        db = get_database()
        config = db.get_user_adapter_config(user_id, 'hydrooj')
        
        if not config:
            raise RuntimeError("HydroOJ未配置，请在GUI中填写配置后再试")
        
        # 检查必需字段
        if not config.get('base_url') or not config.get('domain'):
            raise RuntimeError("HydroOJ配置不完整，请在GUI中填写 base_url 和 domain")
        
        # 检查认证信息
        has_cookie = bool(config.get('sid') or config.get('cookie'))
        if not has_cookie:
            raise RuntimeError("HydroOJ Cookie未配置，请在GUI中填写 sid 后再试")
        
        return config
    
    def _get_user_id_from_context(self) -> int:
        """从 context 中获取 user_id
        
        Returns:
            用户ID
        
        Raises:
            RuntimeError: 未设置用户上下文
        """
        user_id = None
        if hasattr(self, '_context') and isinstance(self._context, dict):
            user_id = self._context.get('user_id')
        
        if not user_id:
            raise RuntimeError("HydroOJ适配器缺少用户上下文，无法加载配置。请确保已登录。")
        
        return user_id
    
    def _ensure_config(self):
        """从数据库加载用户配置（严格用户隔离）
        
        从 context 中获取 user_id，然后从数据库读取用户配置。
        不使用系统配置，不缓存配置到共享实例。
        
        注意：适配器是共享的，但配置应该按用户隔离，所以每次调用都重新加载配置。
        """
        try:
            from loguru import logger
            import re
            
            # 从 context 获取 user_id
            user_id = self._get_user_id_from_context()
            
            # 从数据库读取用户配置
            hydro_config = self._get_user_config(user_id)
            
            # 应用配置
            self.base_url = hydro_config.get("base_url", "https://hydro.ac").strip().rstrip("/")
            # 清理base_url，确保不包含 /d/domain 部分
            self.base_url = re.sub(r'/d/[^/]+/?$', '', self.base_url.strip()).rstrip("/")
            
            self.domain = hydro_config.get("domain", "system")
            self.preferred_prefix = hydro_config.get("preferred_prefix", "")
            
            # 构建 Cookie
            sid = hydro_config.get("sid", "").strip()
            sid_sig = hydro_config.get("sid_sig", "").strip()
            
            if sid:
                parts = [f"sid={sid}"]
                if sid_sig:
                    parts.append(f"sid.sig={sid_sig}")
                self.cookie = "; ".join(parts)
            else:
                # 兼容旧格式
                self.cookie = hydro_config.get("cookie", "")
            
            logger.debug(f"[HydroOJ] 从用户配置加载: user_id={user_id}, base_url={self.base_url}, domain={self.domain}")
            
            # 注意：适配器是共享的，但配置应该按用户隔离
            # 每次调用都重新加载用户配置，不缓存配置到共享实例
            # 同时需要重置 _data_uploader 和 _solution_submitter，因为它们可能使用了旧的配置
            self._data_uploader = None
            self._solution_submitter = None
            
        except Exception as e:
            from loguru import logger
            logger.error(f"加载HydroOJ配置失败: {e}")
            raise
    
    def get_config_schema(self) -> Dict[str, Any]:
        """返回配置schema（用于GUI生成配置表单）"""
        return {
            "base_url": {
                "type": "string", 
                "label": "HydroOJ URL", 
                "default": "https://hydro.ac",
                "required": True,
                "tooltip": "HydroOJ 基础URL，如 https://hydro.ac 或 https://jooj.top"
            },
            "domain": {
                "type": "string", 
                "label": "Domain（域）", 
                "default": "system",
                "required": True,
                "tooltip": "从网页URL中获取，如 https://xxx/d/polygon_test/problem/... 中的 polygon_test"
            },
            "sid": {
                "type": "string", 
                "label": "sid", 
                "required": False,
                "tooltip": "从浏览器开发者工具中复制 sid 的值",
                "is_cookie_part": True  # 标记这是 Cookie 的一部分
            },
            "sid_sig": {
                "type": "string", 
                "label": "sid.sig", 
                "required": False,
                "tooltip": "从浏览器开发者工具中复制 sid.sig 的值（可选）",
                "is_cookie_part": True  # 标记这是 Cookie 的一部分
            },
            "preferred_prefix": {
                "type": "string", 
                "label": "题号前缀（可选）", 
                "default": "P",
                "required": False,
                "tooltip": "题号前缀，如 P、T 等"
            }
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        required = ["base_url", "domain"]
        for field in required:
            if not config.get(field):
                return False, f"缺少必需配置: {field}"
        
        # Cookie可选，如果提供了 sid 则验证
        sid = config.get('sid', '').strip()
        if sid and len(sid) < 10:  # 简单验证长度
            return False, "sid 值似乎不正确"
        
        return True, ""
    
    def get_data_uploader(self) -> DataUploader:
        """获取数据上传器"""
        self._ensure_config()  # 确保配置已加载
        if not self._data_uploader:
            from .data_uploader_impl import HydroOJDataUploader
            self._data_uploader = HydroOJDataUploader(
                base_url=self.base_url,
                domain=self.domain,
                preferred_prefix=self.preferred_prefix
            )
        return self._data_uploader
    
    def get_solution_submitter(self) -> SolutionSubmitter:
        """获取解题提交器"""
        self._ensure_config()  # 确保配置已加载
        if not self._solution_submitter:
            from .solution_submitter_impl import HydroOJSolutionSubmitter
            self._solution_submitter = HydroOJSolutionSubmitter(
                base_url=self.base_url,
                domain=self.domain
            )
        return self._solution_submitter
    
    def login(self):
        """创建认证对象（使用Cookie或Selenium）"""
        from .auth import HydroOJAuth
        from pathlib import Path
        from loguru import logger
        
        # 确保配置已加载
        self._ensure_config()
        
        logger.debug(f"[HydroOJ] 创建认证对象")
        logger.debug(f"[HydroOJ] Base URL: {self.base_url}")
        logger.debug(f"[HydroOJ] Domain: {self.domain}")
        
        auth = HydroOJAuth(self.base_url, self.domain)
        
        # 优先使用配置的Cookie
        if self.cookie:
            logger.info(f"[HydroOJ] 使用配置的 Cookie 进行认证")
            auth.login_with_cookie(self.cookie)
        else:
            logger.info(f"[HydroOJ] 未找到配置的 Cookie，尝试从文件加载")
            # 尝试从文件加载
            if not auth.load_cookies_from_file():
                logger.warning(f"[HydroOJ] 文件中也未找到 Cookie，使用 Selenium 登录")
                # 都没有则使用Selenium登录
                cookie_str = auth.login_with_selenium()
                # 保存到配置
                self.cookie = cookie_str
        
        return auth
    
    def upload_and_update_problem(self, auth: Any, original_id: str, zip_path: str, 
                                   log_callback=None, skip_update: bool = False) -> Dict[str, Any]:
        """完整上传流程（HydroOJ简化版：直接上传即创建）
        
        Args:
            auth: 认证对象（如果传入的不是 HydroOJAuth，会自动创建）
            original_id: 原始题目ID或URL
            zip_path: 测试数据zip路径
            log_callback: 日志回调函数
            
        Returns:
            上传结果
        """
        def _log(msg: str):
            if log_callback:
                log_callback(original_id, msg)
            else:
                from loguru import logger
                logger.info(f"[{original_id}] {msg}")
        
        # 检查 auth 是否是 HydroOJ 的 auth
        from .auth import HydroOJAuth
        from loguru import logger
        
        if not isinstance(auth, HydroOJAuth):
            # 传入的不是 HydroOJ 的 auth，需要创建新的
            logger.debug(f"[HydroOJ] 检测到传入的 auth 不是 HydroOJAuth 类型，自动创建 HydroOJ 认证对象")
            _log("创建 HydroOJ 认证对象...")
            auth = self.login()
        
        _log("开始上传到 HydroOJ...")
        
        # 使用与pipeline相同的规范化逻辑获取canonical_id
        canonical_id = self._get_canonical_id(original_id)
        
        _log(f"题目ID: {canonical_id}")
        _log(f"Domain: {self.domain}")
        
        try:
            # 获取上传器并上传
            uploader = self.get_data_uploader()
            result = uploader.upload_testcase(canonical_id, Path(zip_path), auth, skip_update=skip_update)
            
            # 验证上传结果
            if result.get("status") == "success" or result.get("code") in (0, 200):
                _log(f"✓ 上传成功: {result.get('file', 'unknown')}")
                
                # 检查并记录 real_id（HydroOJ 创建题目后返回的真实ID）
                real_id = result.get("real_id")
                if real_id:
                    _log(f"题目真实ID: {real_id}")
                    logger.debug(f"[HydroOJ] 题目 {canonical_id} 对应的 HydroOJ 真实ID: {real_id}")
                
                return {"status": "success", "response": result}
            else:
                error_msg = result.get("error", "未知错误")
                _log(f"✗ 上传失败: {error_msg}")
                raise RuntimeError(f"上传失败: {error_msg}")
        except RuntimeError as e:
            # 重新抛出运行时错误（通常是认证失败）
            error_msg = str(e)
            _log(f"✗ {error_msg}")
            if "Cookie" in error_msg or "login" in error_msg.lower() or "auth" in error_msg.lower():
                raise RuntimeError(f"{error_msg}\n提示: 请检查 HydroOJ 配置中的 sid 和 sid.sig 是否正确，或使用'自动获取 Cookie'功能重新获取。")
            raise
        except Exception as e:
            # 其他异常
            error_msg = str(e)
            _log(f"✗ 上传失败: {error_msg}")
            raise RuntimeError(f"上传失败: {error_msg}")
    
    def _get_canonical_id(self, original_id: str) -> str:
        """获取规范化ID（与pipeline逻辑一致）
        
        Args:
            original_id: 原始题目ID或URL
            
        Returns:
            规范化ID（适配器_解析ID格式）
        """
        try:
            # 对于URL类型的original_id，使用适配器注册表解析
            if original_id.startswith("https://") or original_id.startswith("http://"):
                from ....oj.registry import get_global_registry
                registry = get_global_registry()
                if registry:
                    adapter = registry.find_adapter_by_url(original_id)
                    if adapter:
                        fetcher = adapter.get_problem_fetcher()
                        if fetcher:
                            parsed_id = fetcher.parse_problem_id(original_id)
                            if parsed_id:
                                return f"{adapter.name}_{parsed_id}"
            
            # 对于manual://格式
            if "://" in original_id:
                return original_id.split("://")[1]
            
            # 其他情况直接返回
            return original_id
        except Exception as e:
            from loguru import logger
            logger.debug(f"[{original_id}] 解析适配器ID失败: {e}")
            return original_id

