# -*- coding: utf-8 -*-
"""SHSOJ适配器（完整实现）"""

from typing import Set, Optional, Dict, Any, List
from pathlib import Path
from loguru import logger
import time

from ...base import OJAdapter, OJCapability, ProblemFetcher, DataUploader, SolutionSubmitter, TrainingManager


class SHSOJAdapter(OJAdapter):
    """SHSOJ适配器（v7.0重构版）
    
    SHSOJ完整功能适配器
    """
    
    def __init__(
        self,
        base_url: str = "",
        username: str = "",
        password: str = "",
        timeout: int = 300,
        proxies: Optional[dict] = None,
        verify_ssl: Optional[bool] = True,
    ):
        """初始化SHSOJ适配器
        
        支持无参构造，首次使用时会自动从 config.json 加载配置。
        """
        # 调用基类的__init__
        super().__init__()
        
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.username = username
        self.password = password
        self.timeout = timeout
        self.proxies = proxies
        self.verify_ssl = verify_ssl if verify_ssl is not None else True

        # 配置是否已加载（手动传入完整参数时视为已加载）
        self._config_loaded = bool(self.base_url and self.username and self.password)
        
        # 延迟初始化各功能模块
        self._problem_fetcher = None
        self._data_uploader = None
        self._solution_submitter = None
        self._training_manager = None
        self._auth_module = None
        self._batch_adapter = None
    
    def _do_initialize(self, context: Dict[str, Any]) -> bool:
        """SHSOJ特定的初始化逻辑
        
        Args:
            context: 初始化上下文
        
        Returns:
            是否初始化成功
        """
        try:
            # 从context中获取配置并加载
            self._ensure_config()
            logger.info(f"SHSOJ适配器配置加载成功: {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"SHSOJ适配器配置加载失败: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查（增强版）"""
        base_health = super().health_check()
        
        # 添加SHSOJ特定的健康信息
        base_health["config_loaded"] = self._config_loaded
        base_health["base_url"] = self.base_url
        base_health["has_auth"] = bool(self.username and self.password)
        
        return base_health

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    # SHSOJ 固定地址（不需要用户配置）
    SHSOJ_BASE_URL = "https://oj.shsbnu.net"
    SHSOJ_API_URL = "https://oj-api.shsbnu.net"
    
    def _get_user_config(self, user_id: int) -> Dict[str, Any]:
        """获取用户的适配器配置（严格用户隔离）
        
        Args:
            user_id: 用户ID（必需）
        
        Returns:
            用户配置字典（包含 username, password 等）
            注意：base_url 已写死，不从用户配置读取
        
        Raises:
            RuntimeError: 用户未配置
        """
        from core.database import get_database
        
        db = get_database()
        config = db.get_user_adapter_config(user_id, 'shsoj')
        
        if not config:
            raise RuntimeError("SHSOJ账号未配置，请在GUI中填写用户名和密码后再试")
        
        # 获取并验证配置字段（trim 前后空格）
        username = (config.get('username') or "").strip()
        password = (config.get('password') or "").strip()
        
        if not username or not password:
            logger.error(f"[SHSOJ] 配置验证失败: username={'有值' if config.get('username') else '空'}, password={'有值' if config.get('password') else '空'}")
            raise RuntimeError("SHSOJ账号未配置，请在GUI中填写用户名和密码后再试")
        
        # 强制使用固定 base_url（忽略用户配置中的 base_url，保证兼容性）
        config['base_url'] = self.SHSOJ_BASE_URL
        
        # 返回 trim 后的配置
        config['username'] = username
        config['password'] = password
        
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
            raise RuntimeError("SHSOJ适配器缺少用户上下文，无法加载配置。请确保已登录。")
        
        return user_id
    
    def _ensure_config(self):
        """确保适配器已经加载配置（严格用户隔离）

        从 context 中获取 user_id，然后从数据库读取用户配置。
        不使用系统配置，不缓存配置到共享实例。
        
        注意：适配器是共享的，但配置应该按用户隔离，所以每次调用都重新加载配置。
        """
        try:
            # 从 context 获取 user_id
            user_id = self._get_user_id_from_context()
            
            # 从数据库读取用户配置
            user_config = self._get_user_config(user_id)
            
            # 应用配置（不缓存，每次读取）
            # 重要：对用户名和密码进行 trim，避免前后空格导致登录失败
            self.base_url = user_config.get('base_url', "https://oj.shsbnu.net").rstrip("/")
            self.username = (user_config.get('username', "") or "").strip()
            self.password = (user_config.get('password', "") or "").strip()
            
            logger.debug(f"[SHSOJ] 从用户配置加载: user_id={user_id}, base_url={self.base_url}, username={self.username}, password_length={len(self.password)}")

            # 加载系统级配置（代理、超时等非敏感配置）
            from services.unified_config import get_config_manager
            cfg_mgr = get_config_manager()
            cfg = cfg_mgr.cfg

            # 超时使用配置文件（分钟）
            try:
                self.timeout = max(30, int(cfg.request_timeout_minutes) * 60)
            except Exception:
                self.timeout = max(self.timeout or 300, 30)

            # 代理设置（系统级别，所有用户共享）
            if getattr(cfg, "proxy_enabled", False):
                proxy_dict: Dict[str, str] = {}
                if cfg.http_proxy:
                    proxy_dict["http"] = cfg.http_proxy
                if cfg.https_proxy:
                    proxy_dict["https"] = cfg.https_proxy
                self.proxies = proxy_dict or None
            else:
                self.proxies = None

            # SSL校验
            if getattr(cfg, "verify_ssl", None) is not None:
                self.verify_ssl = cfg.verify_ssl

            # 注意：适配器是共享的，但配置应该按用户隔离
            # 每次调用都重新加载用户配置，不缓存配置到共享实例
            # 同时需要重置各个功能模块，因为它们可能使用了旧的配置
            self._problem_fetcher = None
            self._data_uploader = None
            self._solution_submitter = None
            self._training_manager = None
            self._auth_module = None
            self._batch_adapter = None

        except Exception as exc:
            logger.error(f"加载SHSOJ适配器配置失败: {exc}")
            raise
    
    @property
    def name(self) -> str:
        return "shsoj"
    
    @property
    def display_name(self) -> str:
        return "SHSOJ"
    
    @property
    def capabilities(self) -> Set[OJCapability]:
        return {
            OJCapability.FETCH_PROBLEM,
            OJCapability.UPLOAD_DATA,
            OJCapability.SUBMIT_SOLUTION,
            OJCapability.MANAGE_TRAINING,
            OJCapability.JUDGE_STATUS,
            OJCapability.BATCH_FETCH,
        }
    
    def get_problem_fetcher(self) -> Optional[ProblemFetcher]:
        self._ensure_config()
        if not self._problem_fetcher:
            from .problem_fetcher_impl import SHSOJProblemFetcher
            self._problem_fetcher = SHSOJProblemFetcher(
                base_url=self.base_url,
                timeout=self.timeout,
                proxies=self.proxies,
                verify_ssl=self.verify_ssl
            )
        return self._problem_fetcher
    
    def get_data_uploader(self) -> Optional[DataUploader]:
        self._ensure_config()
        if not self._data_uploader:
            from .data_uploader_impl import SHSOJDataUploader
            self._data_uploader = SHSOJDataUploader(
                base_url=self.base_url,
                timeout=self.timeout,
                proxies=self.proxies,
                verify_ssl=self.verify_ssl
            )
        return self._data_uploader
    
    def get_solution_submitter(self) -> Optional[SolutionSubmitter]:
        self._ensure_config()
        if not self._solution_submitter:
            from .solution_submitter_impl import SHSOJSolutionSubmitter
            self._solution_submitter = SHSOJSolutionSubmitter(
                base_url=self.base_url,
                timeout=self.timeout,
                proxies=self.proxies,
                verify_ssl=self.verify_ssl
            )
        return self._solution_submitter
    
    def get_training_manager(self) -> Optional[TrainingManager]:
        self._ensure_config()
        if not self._training_manager:
            from .training_manager_impl import SHSOJTrainingManager
            self._training_manager = SHSOJTrainingManager(
                base_url=self.base_url,
                timeout=self.timeout,
                proxies=self.proxies,
                verify_ssl=self.verify_ssl
            )
        return self._training_manager
    
    def get_auth_module(self):
        """获取认证模块（内部使用）"""
        self._ensure_config()
        if not self._auth_module:
            from ...shsoj.auth import SHSOJAuth
            self._auth_module = SHSOJAuth(
                base_url=self.base_url,
                timeout=self.timeout,
                proxies=self.proxies,
                verify_ssl=self.verify_ssl
            )
        return self._auth_module
    
    def get_batch_adapter(self):
        """获取批量适配器（按标签批量获取）"""
        if not self._batch_adapter:
            from .batch_adapter_impl import SHSOJBatchAdapter
            self._batch_adapter = SHSOJBatchAdapter(
                base_url=self.base_url or "https://api-tcoj.aicoders.cn",
                timeout=self.timeout
            )
        return self._batch_adapter
    
    def login(self, user_id: Optional[int] = None):
        """登录获取认证
        
        Args:
            user_id: 用户ID（可选，如果提供则使用此ID加载配置，否则使用context中的ID）
        """
        # 如果提供了 user_id，临时设置到 context 中
        if user_id is not None:
            if not hasattr(self, '_context') or not isinstance(self._context, dict):
                self._context = {}
            self._context['user_id'] = user_id
        
        self._ensure_config()
        
        # 验证配置
        if not self.username or not self.password:
            logger.error(f"[SHSOJ] 登录失败：配置不完整 - username={'已设置' if self.username else '未设置'}, password={'已设置' if self.password else '未设置'}")
            raise RuntimeError("SHSOJ账号未配置，请在GUI中填写用户名和密码后再试")
        
        # 记录登录信息（不记录密码）
        logger.info(f"[SHSOJ] 开始登录: base_url={self.base_url}, username={self.username}, password_length={len(self.password)}")
        
        auth_module = self.get_auth_module()
        try:
            auth = auth_module.login_user(self.username, self.password)
            logger.info(f"[SHSOJ] 登录成功")
            return auth
        except Exception as e:
            logger.error(f"[SHSOJ] 登录失败: {e}")
            logger.debug(f"[SHSOJ] 登录详情: base_url={self.base_url}, username={self.username}")
            raise
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置schema
        
        注意：base_url 已写死为 https://oj.shsbnu.net，不需要用户配置
        """
        return {
            # base_url 已移除，使用固定地址
            "username": {
                "type": "string",
                "label": "用户名",
                "placeholder": "请输入SHSOJ用户名",
                "required": True
            },
            "password": {
                "type": "password",
                "label": "密码",
                "placeholder": "请输入SHSOJ密码",
                "required": True
            }
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置
        
        只需要验证用户名和密码，base_url 已写死
        """
        # 只检查用户名和密码（base_url 已写死）
        if not config.get("username"):
            return False, "缺少必需配置: 用户名"
        if not config.get("password"):
            return False, "缺少必需配置: 密码"
        return True, ""
    
    def check_problem_exists(self, auth, problem_id: str) -> tuple[bool, int | None]:
        """检查题目是否存在（通过problemId查找）"""
        self._ensure_config()
        case_module = self.get_data_uploader()
        if not case_module:
            raise RuntimeError("无法获取数据上传器")
        return case_module.check_problem_exists(auth, problem_id)
    
    def create_problem(self, auth, problem_data: Dict[str, Any], upload_testcase_dir: str) -> Dict[str, Any]:
        """创建新题目"""
        self._ensure_config()
        case_module = self.get_data_uploader()
        if not case_module:
            raise RuntimeError("无法获取数据上传器")
        return case_module.create_problem(auth, problem_data, upload_testcase_dir)
    
    def fetch_problem_cases(self, auth: Any, actual_id: int) -> List[Dict[str, Any]]:
        """获取题目的测试用例列表"""
        self._ensure_config()
        case_module = self.get_data_uploader()
        if not case_module:
            return []
        return case_module.fetch_problem_cases(auth, actual_id)
    
    def _fetch_shsoj_tags(self, auth: Any) -> List[Dict[str, Any]]:
        """获取 SHSOJ 后端所有可用标签（用于名称匹配）
        
        调用 /api/get-problem-tags-group 接口获取标签组，
        然后扁平化所有标签对象
        """
        import requests
        
        url = f"{self.base_url.replace('oj.', 'oj-api.')}/api/get-problem-tags-group"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "authorization": auth.token,
            "url-type": "general",
            "User-Agent": "Mozilla/5.0",
        }
        
        try:
            r = auth.session.get(url, headers=headers, timeout=self.timeout, 
                                proxies=self.proxies, verify=self.verify_ssl)
            if r.status_code != 200:
                return []
            
            data = r.json()
            if data.get("code") not in (0, 200):
                return []
            
            # 响应格式：{"code": 0, "data": [{"id": 1, "name": "组名", "tagList": [...]}, ...]}
            tag_groups = data.get("data", []) or []
            all_tags = []
            
            for group in tag_groups:
                tag_list = group.get("tagList", [])
                if isinstance(tag_list, list):
                    all_tags.extend(tag_list)
            
            return all_tags
        except Exception as e:
            logger.debug(f"获取 SHSOJ 标签失败: {e}")
            return []
    
    def fetch_admin_problem(self, auth: Any, actual_id: int) -> Dict[str, Any]:
        """获取管理员视角的题目信息"""
        self._ensure_config()
        from .problem_fetcher_impl import SHSOJProblemFetcher
        problem_module = SHSOJProblemFetcher(
            base_url=self.base_url,
            timeout=self.timeout,
            proxies=self.proxies,
            verify_ssl=self.verify_ssl
        )
        return problem_module.fetch_admin_problem(auth, actual_id)
    
    def update_problem_config(self, auth: Any, actual_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新题目配置"""
        self._ensure_config()
        case_module = self.get_data_uploader()
        if not case_module:
            raise RuntimeError("无法获取数据上传器")
        return case_module.put_admin_problem(auth, actual_id, payload)
    
    def upload_and_update_problem(self, auth: Any, original_id: str, zip_path: str, 
                                   log_callback=None, skip_update: bool = False) -> Dict[str, Any]:
        """上传测试数据并更新题目配置（SHSOJ完整实现）
        
        完整流程：
        1. 解析或创建题目ID（适配器自己判断）
        2. 上传zip文件（如果还没上传）
        3. 获取测试用例列表
        4. 获取当前题目配置
        5. 构建更新payload（SHSOJ特定格式）
        6. 更新题目配置
        """
        self._ensure_config()
        from pathlib import Path
        import json
        import time
        import copy
        from utils.text import sanitize_filename
        from services.oj.registry import get_global_registry
        
        def _log(msg: str):
            if log_callback:
                log_callback(original_id, msg)
            else:
                logger.info(f"[{original_id}] {msg}")
        
        # 如果 auth 为 None，自动创建认证对象
        if auth is None:
            _log("检测到 auth 为 None，自动创建 SHSOJ 认证对象...")
            try:
                auth = self.login()
                _log("✓ 登录成功")
            except Exception as e:
                error_msg = f"自动登录失败: {e}"
                _log(f"✗ {error_msg}")
                raise RuntimeError(f"{error_msg}\n提示: 请检查配置中的用户名和密码是否正确。")
        
        # Step 1: 解析或创建题目ID
        _log("Step 1/5: 解析实际题号或创建新题目...")
        _log(f"  原始输入ID: {original_id} (类型: {type(original_id).__name__})")
        
        # 从 zip_path 推断工作区目录
        # zip_path 格式: workspace/user_{user_id}/problem_{problem_id}/xxx.zip
        if not zip_path:
            raise ValueError("zip_path 参数不能为空")
        
        zip_path_obj = Path(zip_path)
        workspace_dir = zip_path_obj.parent  # zip 文件所在目录就是工作区
        
        # 调用resolve_or_create_problem_id（适配器自己判断）
        actual_id, problem_id_str, upload_result_created = self.resolve_or_create_problem_id(
            auth, original_id, zip_path, workspace_dir
        )
        
        if not actual_id:
            raise RuntimeError(f"无法解析或创建题目ID: {original_id}")
        
        if upload_result_created:
            _log(f"✓ 创建新题目成功: 后端ID={actual_id}, problemId={problem_id_str}")
        else:
            _log(f"✓ 解析成功: 后端ID={actual_id}, problemId={problem_id_str}")
        
        # Step 2: 上传ZIP文件（如果创建新题目时已上传则跳过）
        upload_result = None
        file_dir = None
        file_list = []
        
        if upload_result_created:
            file_dir = upload_result_created.get("fileListDir") or upload_result_created.get("dir") or ""
            file_list = upload_result_created.get("fileList", [])
            upload_result = upload_result_created
            _log("Step 2/5: 测试数据包已在上一步上传，跳过")
        else:
            _log("Step 2/5: 上传测试数据包...")
            _log(f"  文件路径: {zip_path}")
            case_module = self.get_data_uploader()
            if not case_module:
                raise RuntimeError("无法获取数据上传器")
            
            upload_result = case_module.upload_testcase_zip(auth, zip_path)
            file_dir = upload_result.get("fileListDir") or upload_result.get("dir") or ""
            file_list = upload_result.get("fileList", [])
            
            if not file_dir:
                raise RuntimeError(f"上传响应缺少目录字段: {upload_result}")
            
            _log("✓ 上传成功")
            _log(f"  服务器目录: {file_dir}")
            _log(f"  文件数量: {len(file_list)}")
            for idx, item in enumerate(file_list[:3], 1):
                _log(f"    {idx}. {item.get('input')} / {item.get('output')}")
            if len(file_list) > 3:
                _log(f"    ... 等共 {len(file_list)} 个文件")
        
        # Step 3: 触发提取上传的测试用例（可选）
        try:
            # 按照本地上传（gen.py产物）的数量作为基准
            expected = len(file_list) if file_list else 0
            parsed_cases = []
            for attempt in range(12):  # 最多等待 ~12s
                parsed_cases = self.fetch_problem_cases(auth, actual_id) or []
                if len(parsed_cases) >= expected:
                    break
                if attempt == 0:
                    _log(f"从服务器解析了 {len(parsed_cases)} 个测试用例，等待解析完成...")
                time.sleep(1)
            if len(parsed_cases) < expected:
                _log(f"⚠ 服务器仅解析到 {len(parsed_cases)}/{expected} 个测试用例，继续使用本地上传列表（{len(file_list)} 个）")
            else:
                _log(f"从服务器解析了 {len(parsed_cases)} 个测试用例")
        except Exception as e:
            logger.debug(f"[{original_id}] fetch_problem_cases失败: {e}")
            _log("⚠ 获取服务器解析用例失败，继续使用本地上传列表")
        
        # Step 4: 获取当前题目配置
        _log(f"Step 3/5: 获取题目当前配置（使用后端ID {actual_id}）...")
        try:
            problem_data = self.fetch_admin_problem(auth, actual_id)
            if problem_data:
                title = problem_data.get('title', 'N/A')
                _log(f"✓ 获取到后端ID {actual_id} 的题目数据")
                _log(f"  题目标题: {title}")
                _log(f"  judgeMode: {problem_data.get('judgeMode', 'default')}")
            else:
                raise RuntimeError(f"无法获取问题 {actual_id} 的配置数据，取消更新。")
        except Exception as e:
            _log(f"✗ 获取配置失败: {e}")
            raise
        
        # Step 5: 加载模板并构建payload
        _log("Step 4/5: 构建更新payload...")
        _log("  加载上传模板...")
        
        # 模板路径：src/services/upload_template.json
        # __file__ = .../src/services/oj/adapters/shsoj/adapter.py
        # parent x4 = .../src/services
        template_path = Path(__file__).parent.parent.parent.parent / "data" / "upload_template.json"
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)
        except Exception as e:
            error_msg = f"加载上传模板失败: {e}，模板文件路径: {template_path}"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        # 验证模板必需字段
        if "languages" not in template:
            error_msg = "模板缺少必需字段: languages"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        if not isinstance(template["languages"], list) or len(template["languages"]) == 0:
            error_msg = "模板中 languages 字段为空或无效（必须是非空数组）"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        if "codeTemplates" not in template:
            error_msg = "模板缺少必需字段: codeTemplates"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        if "problem" not in template:
            error_msg = "模板缺少必需字段: problem"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        if not isinstance(template["problem"], dict):
            error_msg = "模板中 problem 字段必须是对象"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        _log(f"  模板加载成功，包含 {len(template.get('languages', []))} 个语言")
        
        # 按照原始脚本逻辑准备上传payload（完整保留所有字段）
        payload = copy.deepcopy(template)
        
        # 设置顶层标志
        payload["isUploadTestCase"] = True
        payload["uploadTestcaseDir"] = file_dir  # 关键：必须设置服务器返回的目录路径
        payload["changeModeCode"] = True
        
        # 使用当前问题的judgeMode（如果有）
        payload["judgeMode"] = problem_data.get("judgeMode", payload.get("judgeMode", "default"))
        # changeJudgeCaseMode 在顶层 - HAR 抓包显示为 false（不是 true）
        # 参考 HAR 文件：成功的 PUT 请求中 changeJudgeCaseMode=false
        payload["changeJudgeCaseMode"] = False
        
        # 更新嵌套的problem字段
        prob = payload.get("problem", {})
        
        # 先从本地 problem_data.json 读取题目信息（从 Aicoders 拉取的，优先级最高）
        local_data = {}
        try:
            # 使用 registry 获取 canonical_id
            registry = get_global_registry()
            canonical_id = original_id
            if registry:
                stripped = original_id.strip()
                is_pure_numeric = stripped.isdigit() and 1 <= len(stripped) <= 10
                adapter = None
                lookup_id = stripped
                parsed_id = None
                
                if is_pure_numeric:
                    # 纯数字场景，使用默认平台构造 URL 再解析
                    from services.unified_config import get_config_manager
                    cfg_mgr = get_config_manager()
                    default_base_url = getattr(cfg_mgr.cfg, 'default_oj_base_url', 'https://oj.shsbnu.net')
                    constructed_url = f"{default_base_url}/problem/{stripped}"
                    adapter = registry.find_adapter_by_url(constructed_url)
                    lookup_id = constructed_url if adapter else stripped
                else:
                    adapter = registry.find_adapter_by_url(stripped)
                    lookup_id = stripped
                
                if adapter:
                    fetcher = adapter.get_problem_fetcher()
                    if fetcher:
                        try:
                            parsed_id = fetcher.parse_problem_id(lookup_id)
                        except Exception:
                            parsed_id = None
                    if parsed_id:
                        canonical_id = f"{adapter.name}_{parsed_id}"
                    elif is_pure_numeric:
                        canonical_id = f"{adapter.name}_{stripped}"
                    else:
                        canonical_id = original_id
            
            # 使用已传入的 workspace_dir
            if not workspace_dir or not workspace_dir.exists():
                raise ValueError(f"workspace_dir 无效或不存在: {workspace_dir}")
            
            local_data_file = workspace_dir / "problem_data.json"
            
            if local_data_file.exists():
                with open(local_data_file, 'r', encoding='utf-8') as f:
                    local_data = json.load(f)
                _log(f"  ✓ 读取到本地题目数据: {local_data.get('title', 'N/A')}")
        except Exception as e:
            logger.debug(f"[{original_id}] 读取本地 problem_data.json 失败: {e}")
            local_data = {}
        
        # 再从 SHSOJ 后端数据中读取（作为补充，不覆盖本地数据）
        source_data = problem_data.get("extra", {}).get("raw_data", {})
        if not source_data:
            source_data = problem_data
        
        if not local_data:
            error_msg = "未能读取到本地 problem_data.json，终止本次上传以便重试"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        # 数据合并优先级（从低到高）：
        # 1. 模板默认值（格式参考，不应包含实际数据）
        # 2. SHSOJ 后端数据（只复制已知兼容的字段，防止模板数据覆盖 shsoj 上的数据）
        # 3. 本地 problem_data.json（优先级最高，覆盖关键字段）
        
        # 第一步：使用 SHSOJ 后端数据覆盖已知兼容字段（避免复制不兼容的字段如 extra、samples）
        # 白名单：只复制 SHSOJ 后端 API 接受的字段（与 admin/problem 返回结构一致，参考 wash.py）
        shsoj_compatible_fields = {
            # 基础标识字段
            "id", "problemId", "title", "author", "type", "publishStatus",
            # 评测配置
            "judgeMode", "judgeCaseMode", "timeLimit", "memoryLimit", "stackLimit",
            # 题目内容
            "description", "input", "output", "examples", "hint", "source",
            # 难度与权限
            "difficulty", "difficultyRadix", "auth", "ioScore", "codeShare",
            # SPJ 配置
            "spjCode", "spjLanguage", "spjCompileOk",
            # 额外文件
            "userExtraFile", "judgeExtraFile",
            # 测试数据配置
            "isRemoveEndBlank", "openCaseResult", "isUploadCase", "caseVersion",
            "uploadTestcaseDir", "testCaseScore",
            # 文件IO配置
            "isFileIO", "ioReadFileName", "ioWriteFileName",
            # 元数据字段（从后端返回）
            "modifiedUser", "isGroup", "gid", "applyPublicProgress",
            "gmtCreate", "gmtModified", "isDeleted",
            "questionBankId", "questionChapterId", "realname", "isRemote",
            # 竞赛相关字段由前端单独处理，避免引发解析失败
        }
        for k, v in source_data.items():
            if k in shsoj_compatible_fields:
                prob[k] = v
        
        # 第二步：使用本地数据覆盖关键字段（确保 aicoders 的数据优先）
        if local_data:
            # 关键字段：必须从 local_data 获取，防止使用模板数据
            critical_fields = {
                "title": ["title"],
                "description": ["description", "statement"],
                "input": ["input_format", "input"],
                "output": ["output_format", "output"],
            }
            
            for target_field, source_fields in critical_fields.items():
                value = None
                for sf in source_fields:
                    if sf in local_data and local_data[sf]:
                        value = local_data[sf]
                        break
                
                if value:
                    if target_field == "description":
                        # SHSOJ 只接受 description 字段，不接受 statement
                        prob["description"] = value
                        _log(f"  从本地数据更新字段: {target_field} (长度: {len(value)} 字符)")
                    elif target_field == "title":
                        prob["title"] = value
                        _log(f"  从本地数据更新标题: {value}")
                    else:
                        prob[target_field] = value
                        _log(f"  从本地数据更新字段: {target_field}")
                else:
                    _log(f"  ⚠ 警告：关键字段 {target_field} 在 local_data 中不存在")
            
            # 覆盖其他字段（如果 local_data 中有）
            # hints -> hint
            if local_data.get("hints"):
                prob["hint"] = local_data["hints"]
                _log(f"  从本地数据更新字段: hint (来自 hints)")
            elif local_data.get("hint"):
                prob["hint"] = local_data["hint"]
                _log(f"  从本地数据更新字段: hint")
            
            # samples -> examples (需要转换格式)
            if local_data.get("samples"):
                # 将 Aicoders 的 samples 列表转换为 SHSOJ 的 XML 格式
                samples = local_data["samples"]
                examples_xml = ""
                for sample in samples:
                    inp = sample.get("input", "")
                    out = sample.get("output", "")
                    examples_xml += f"<input>{inp}</input><output>{out}</output>"
                prob["examples"] = examples_xml
                _log(f"  从本地数据更新字段: examples (来自 samples，转换为 XML)")
            elif local_data.get("examples"):
                prob["examples"] = local_data["examples"]
                _log(f"  从本地数据更新字段: examples")
            
            # 如果有 raw_data.examples，优先使用（已经是 XML 格式）
            raw_examples = local_data.get("extra", {}).get("raw_data", {}).get("examples")
            if raw_examples:
                prob["examples"] = raw_examples
                _log(f"  从本地数据更新字段: examples (来自 raw_data)")
            
            # 覆盖其他可能存在的字段（如果 local_data 中有）
            other_fields = ["timeLimit", "memoryLimit", "stackLimit", "difficulty"]
            for field in other_fields:
                if field in local_data:
                    prob[field] = local_data[field]
                    _log(f"  从本地数据更新字段: {field}")
        
        # 检测是否使用了模板的示例数据（防止误上传模板数据）
        template_example_title = template.get("problem", {}).get("title", "")
        if template_example_title and prob.get("title") == template_example_title:
            error_msg = f"检测到题目标题与模板示例数据相同（'{template_example_title}'），可能误用了模板数据，终止上传"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        # 设置必需字段（覆盖）
        prob["id"] = actual_id
        # 关键修复：使用后端返回的实际 problemId（纯数字），而不是传入的原始 ID
        # 如果后端数据中有 problemId，优先使用（通常是纯数字字符串，如 "20040"）
        # 这样可以避免 "P1002" 这类非纯数字 problemId 导致的解析错误
        backend_problem_id = problem_data.get("problemId")
        if backend_problem_id:
            prob["problemId"] = str(backend_problem_id)  # 确保是字符串类型
            _log(f"  使用后端返回的 problemId: {backend_problem_id}")
        else:
            # 如果后端没有返回 problemId，使用传入的 ID（fallback）
            prob["problemId"] = problem_id_str
            _log(f"  后端未返回 problemId，使用传入的 ID: {problem_id_str}")
        prob["isUploadCase"] = True
        # 关键：必须设置为服务器返回的实际目录路径（与旧代码一致）
        prob["uploadTestcaseDir"] = file_dir
        prob["caseVersion"] = str(int(time.time() * 1000))
        prob["judgeMode"] = payload["judgeMode"]
        # judgeCaseMode 在 problem 内，从 problem_data 或模板获取
        prob["judgeCaseMode"] = problem_data.get("judgeCaseMode", prob.get("judgeCaseMode", "default"))
        
        # 确保 type 字段存在且正确（ACM=0, OI=1）
        # 优先级：1. local_data 2. source_data 3. 模板的 problem 对象
        if "type" not in prob or prob["type"] not in (0, 1):
            # 尝试从 local_data 获取
            if local_data.get("type") in (0, 1):
                prob["type"] = local_data["type"]
                _log(f"  从本地数据获取 type 字段: {prob['type']}")
            # 尝试从 source_data 获取
            elif source_data.get("type") in (0, 1):
                prob["type"] = source_data["type"]
                _log(f"  从后端数据获取 type 字段: {prob['type']}")
            # 尝试从模板的 problem 对象获取
            elif template.get("problem", {}).get("type") in (0, 1):
                prob["type"] = template["problem"]["type"]
                _log(f"  从模板获取 type 字段: {prob['type']}")
            else:
                error_msg = "无法获取 type 字段（从本地数据、后端数据和模板都获取不到或值无效，必须是 0(ACM) 或 1(OI)）"
                _log(f"  ✗ {error_msg}")
                raise RuntimeError(error_msg)
        
        # 确保关键数值字段不为 null（SHSOJ API 不接受 null 值）
        # 参考抓包数据，这些字段应该有具体的数值而非 null
        numeric_defaults = {
            "difficulty": 0,
            "difficultyRadix": 0,
            "auth": 1,
            "ioScore": 100,
            "publishStatus": 1,
        }
        for field, default_val in numeric_defaults.items():
            if prob.get(field) is None:
                prob[field] = default_val
        
        # 确保布尔字段不为 null
        bool_defaults = {
            "codeShare": False,
            "isRemoveEndBlank": True,
            "openCaseResult": True,
            "isFileIO": False,
            "isGroup": False,
            "isRemote": False,
            "spjCompileOk": False,
        }
        for field, default_val in bool_defaults.items():
            if prob.get(field) is None:
                prob[field] = default_val
        
        # 确保字符串字段不为 null（空字符串）
        string_defaults = ["author", "source", "hint"]
        for field in string_defaults:
            if prob.get(field) is None:
                prob[field] = ""
        
        # 生成测试点分值（均分100分）
        n = max(1, len(file_list))
        base = 100 // n
        extra = 100 - base * n
        scores = []
        for i, it in enumerate(file_list, start=1):
            score = base + (1 if i <= extra else 0)
            # 字段顺序与 HAR 抓包数据一致：output, input, score, pid, index, _XID
            # 注意：HAR 文件中 output 在前，input 在后
            scores.append({
                "output": it.get("output") or "", 
                "input": it.get("input") or "", 
                "score": score, 
                "pid": actual_id, 
                "index": i,
                "_XID": f"row_{i + 5}"
            })
        prob["testCaseScore"] = scores
        payload["problem"] = prob
        
        # 设置samples
        payload["samples"] = scores
        
        # 从后端数据或模板获取 languages（必需字段）
        # 优先级：1. problem_data（后端数据） 2. 模板
        if problem_data.get("languages") and isinstance(problem_data["languages"], list) and len(problem_data["languages"]) > 0:
            payload["languages"] = problem_data["languages"]
            _log(f"  从后端数据获取 {len(payload['languages'])} 个语言配置")
        elif template.get("languages") and isinstance(template["languages"], list) and len(template["languages"]) > 0:
            payload["languages"] = template["languages"]
            _log(f"  从模板获取 {len(payload['languages'])} 个语言配置")
        else:
            error_msg = "无法获取 languages 配置（从后端数据和模板都获取不到或无效，必须是非空数组）"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        # SHSOJ 标签上传已禁用，强制清空
        payload["tags"] = []
        _log("  已禁用标签同步，payload.tags 设为空数组")
        
        # codeTemplates：前端更新请求中为空，避免发送模板内容导致解析失败
        if "codeTemplates" not in template:
            error_msg = "模板中缺少 codeTemplates 字段"
            _log(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg)
        payload["codeTemplates"] = []
        
        _log(f"  计算测试点分值（{len(file_list)}个文件均分100分）...")
        _log(f"  生成 {len(scores)} 个测试点，每个分值: {[s['score'] for s in scores[:5]]}...")
        
        # Step 6: 提交更新
        _log("Step 5/5: 提交题目配置更新...")
        _log(f"  更新字段数: {len(payload)}")
        _log(f"  problem字段数: {len(payload.get('problem', {}))}")
        
        resp = self.update_problem_config(auth, actual_id, payload)
        
        # 类型安全：确保 resp 是字典（put_admin_problem 应该总是返回字典）
        if not isinstance(resp, dict):
            error_msg = f"update_problem_config 返回了非字典类型: {type(resp)}, 值: {resp}"
            logger.error(f"[{original_id}] {error_msg}")
            raise RuntimeError(error_msg)
        
        code = resp.get("code", -1)
        if code in (0, 200):
            _log("✓ 题目配置更新成功！")
            _log(f"  响应消息: {resp.get('msg', 'OK')}")
            # 提交后进行一次校验：后端实际用例数量是否与本地一致
            try:
                verify_data = self.fetch_admin_problem(auth, actual_id) or {}
                tc = verify_data.get("testCaseScore") or verify_data.get("problem", {}).get("testCaseScore") or []
                if not isinstance(tc, list):
                    tc = []
                expected_n = len(file_list)
                actual_n = len(tc)
                if actual_n < expected_n:
                    _log(f"⚠ 后端当前测试点数 {actual_n} 小于本地 {expected_n}，尝试触发服务器重新解析后再次更新...")
                    try:
                        _ = self.fetch_problem_cases(auth, actual_id)
                    except Exception:
                        pass
                    # 重新设置版本号并再次提交（避免缓存）
                    prob["caseVersion"] = str(int(time.time() * 1000))
                    resp2 = self.update_problem_config(auth, actual_id, payload)
                    if isinstance(resp2, dict) and resp2.get("code", -1) in (0, 200):
                        _log("✓ 已再次提交题目配置更新（同步用例）")
                    else:
                        _log(f"⚠ 再次更新返回非成功代码: {resp2.get('code') if isinstance(resp2, dict) else 'unknown'}，继续后续流程")
                else:
                    _log(f"✓ 后端测试点数校验通过：{actual_n}/{expected_n}")
            except Exception as ve:
                _log(f"⚠ 提交后校验用例数量时出现异常：{ve}")
        else:
            _log(f"✗ 更新返回非成功代码: {code}")
            _log(f"  响应: {resp}")
            raise RuntimeError(f"更新返回错误码: {code}")
        
        # 保存响应到文件（方便调试）
        try:
            (workspace_dir / "upload_response.json").write_text(
                json.dumps(resp, ensure_ascii=False, indent=2), 
                encoding='utf-8'
            )
        except Exception:
            pass
        
        # 返回结果，包含 real_id 用于后续求解
        # 对于 SHSOJ，提交API需要的是 problemId（字符串），而不是 actual_id（后端ID）
        # 如果后端返回了 problemId，优先使用；否则使用 actual_id 作为 fallback
        # 
        # 类型安全：确保 actual_id 不是 None（防御性编程）
        if actual_id is None:
            raise RuntimeError(f"actual_id 为 None，无法返回有效结果。original_id: {original_id}")
        
        # 获取 problemId（用于提交）- 从多个位置尝试获取
        # 优先级：1. problem_data.problemId（直接字段） 2. problem_data.problem.problemId（嵌套结构）
        #         3. payload.problem.problemId（我们设置的） 4. actual_id（fallback）
        problem_id_for_submit = problem_data.get("problemId")
        if not problem_id_for_submit:
            # 尝试从嵌套结构获取（兼容不同返回格式）
            problem_id_for_submit = problem_data.get("problem", {}).get("problemId")
        if not problem_id_for_submit:
            # 如果后端数据中没有，从 payload 中获取（我们刚刚设置的）
            problem_id_for_submit = payload.get("problem", {}).get("problemId")
        
        # 如果还是没有，使用 actual_id 作为 fallback（转换为字符串）
        if not problem_id_for_submit:
            problem_id_for_submit = str(actual_id)
            _log(f"  未获取到 problemId，使用 actual_id 作为 fallback: {problem_id_for_submit}")
        else:
            problem_id_for_submit = str(problem_id_for_submit)
            _log(f"  使用 problemId 作为提交ID: {problem_id_for_submit}")
        
        # 构建响应对象（resp 已经是字典，直接复制）
        response_with_real_id = resp.copy()
        
        # 确保 response 中包含必要的字段
        response_with_real_id["real_id"] = problem_id_for_submit  # 使用 problemId 而不是 actual_id
        if "code" not in response_with_real_id:
            response_with_real_id["code"] = code  # 添加 code（虽然应该已经存在）
        
        return {
            "status": "success",
            "actual_id": actual_id,
            "real_id": problem_id_for_submit,  # 使用 problemId 作为提交ID（而不是 actual_id）
            "payload": payload,
            "response": response_with_real_id
        }
    
    def resolve_or_create_problem_id(self, auth, original_id: str, zip_path: str = None, workspace_dir: Path = None) -> tuple[int | None, str | None, Dict[str, Any] | None]:
        """解析或创建题目ID（SHSOJ适配器自己判断）
        
        - 如果original_id是SHSOJ格式（数字ID），直接解析
        - 如果不是SHSOJ格式，从problem_data.json创建新题目
        """
        self._ensure_config()
        import json
        
        # 尝试解析为SHSOJ的problemId
        fetcher = self.get_problem_fetcher()
        if fetcher:
            parsed_id = fetcher.parse_problem_id(original_id)
            if parsed_id:
                # 可能是SHSOJ格式，检查题目是否存在
                exists, existing_id = self.check_problem_exists(auth, parsed_id)
                if exists:
                    # 是SHSOJ的题目，直接返回
                    return existing_id, parsed_id, None
                # 如果不存在，判断是否确实是 SHSOJ 的题号（纯数字且来源于 SHSOJ 域）
                original_str = str(original_id).strip()
                is_shsoj_source = original_str.isdigit()
                if not is_shsoj_source:
                    try:
                        is_shsoj_source = bool(fetcher.supports_url(original_str))
                    except Exception:
                        is_shsoj_source = False
                if parsed_id.isdigit() and is_shsoj_source:
                    raise RuntimeError(f"SHSOJ题目不存在: {parsed_id}，请先创建题目")
                logger.debug(f"[{original_id}] 识别为外部平台题目，将尝试在 SHSOJ 创建新题目")
        
        # 不是SHSOJ格式，尝试创建新题目
        # 需要读取本地problem_data.json
        if not workspace_dir or not workspace_dir.exists():
            raise ValueError(f"workspace_dir 无效或不存在: {workspace_dir}")
        
        problem_data_file = workspace_dir / "problem_data.json"
        if not problem_data_file.exists():
            raise RuntimeError(f"无法找到题面数据文件: {problem_data_file}，请先拉取题面")
        
        problem_data = json.loads(problem_data_file.read_text(encoding="utf-8"))
        
        if not zip_path:
            # 尝试从workspace_dir中找到zip文件
            zip_files = list(workspace_dir.glob("problem_*_testcase.zip"))
            if zip_files:
                zip_path = str(zip_files[0])
            else:
                raise RuntimeError(f"无法找到测试数据zip文件，请先生成测试数据")
        
        # 先上传zip文件
        case_module = self.get_data_uploader()
        if not case_module:
            raise RuntimeError("无法获取数据上传器")
        
        upload_result = case_module.upload_testcase_zip(auth, zip_path)
        file_dir = upload_result.get("fileListDir") or upload_result.get("dir") or ""
        file_list = upload_result.get("fileList", [])
        
        if not file_dir:
            raise RuntimeError(f"上传响应缺少目录字段: {upload_result}")
        
        # 从上传的文件列表构建testCaseScore（均分100分）
        n = max(1, len(file_list))
        base = 100 // n
        extra = 100 - base * n
        
        test_case_score = []
        samples_list = []
        for idx, item in enumerate(file_list, 1):
            inp = item.get("input", "") or ""
            out = item.get("output", "") or ""
            score = base + (1 if idx <= extra else 0)
            # 字段顺序与 HAR 抓包数据一致：output, input, score, pid, index, _XID
            # 注意：HAR 文件中 output 在前，input 在后
            test_case_score.append({
                "output": out,
                "input": inp,
                "score": score,
                "pid": None,
                "index": idx,
                "_XID": f"row_{idx + 5}"
            })
            samples_list.append({
                "output": out,
                "input": inp,
                "score": score,
                "pid": None,
                "index": idx,
                "_XID": f"row_{idx + 5}"
            })
        
        # 更新problem_data中的testCaseScore
        problem_data['_test_case_score'] = test_case_score
        problem_data['_samples_list'] = samples_list
        
        # 加载upload_template获取languages等默认配置
        try:
            import json as json_module
            # 使用相对于当前文件的路径，确保在 Docker 环境中也能正确加载
            template_path = Path(__file__).parent.parent.parent.parent / "data" / "upload_template.json"
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json_module.load(f)
            problem_data['_languages'] = template.get('languages', [])
            logger.info(f"[{original_id}] 从模板获取 {len(problem_data['_languages'])} 个语言配置")
        except Exception as e:
            logger.warning(f"[{original_id}] 无法加载 upload_template.json: {e} (路径: {template_path})")
            problem_data['_languages'] = []
        
        # ============ 新增：检查 problemId 是否已存在 ============
        # 获取要使用的 problemId
        problem_id_to_use = str(problem_data.get("id") or problem_data.get("problem_id") or original_id).strip()
        local_title = (problem_data.get("title") or "").strip()
        
        # 检查 SHSOJ 上是否已存在该 problemId 的题目
        exists, existing_actual_id = case_module.check_problem_exists(auth, problem_id_to_use)
        
        if exists and existing_actual_id:
            # 题目已存在，需要比较标题
            logger.info(f"[{original_id}] SHSOJ 上已存在 problemId={problem_id_to_use} (actual_id={existing_actual_id})，检查标题是否一致...")
            
            try:
                # 获取已有题目的详细信息
                existing_problem = self.fetch_admin_problem(auth, existing_actual_id)
                existing_title = ""
                
                if existing_problem and existing_problem.get("data"):
                    prob_info = existing_problem["data"].get("problem", {})
                    existing_title = (prob_info.get("title") or "").strip()
                
                # 比较标题
                if existing_title and local_title:
                    if existing_title == local_title:
                        # 标题一致，返回已有题目ID（更新模式）
                        logger.info(f"[{original_id}] ✓ 标题一致 ('{local_title}')，将更新已有题目")
                        return existing_actual_id, problem_id_to_use, None
                    else:
                        # 标题不一致，报错
                        logger.error(f"[{original_id}] ✗ 标题不一致: 本地='{local_title}', SHSOJ='{existing_title}'")
                        raise RuntimeError(
                            f"SHSOJ 上已存在 problemId={problem_id_to_use}，但标题不一致！\n"
                            f"  本地标题: {local_title}\n"
                            f"  远端标题: {existing_title}\n"
                            f"为避免覆盖错误题目，请更换 problemId 或手动处理。"
                        )
                else:
                    # 无法获取标题信息，警告但继续（更新模式）
                    logger.warning(f"[{original_id}] 无法获取标题信息进行比较，将更新已有题目")
                    return existing_actual_id, problem_id_to_use, None
                    
            except RuntimeError:
                raise  # 重新抛出标题不一致的错误
            except Exception as e:
                logger.warning(f"[{original_id}] 获取已有题目信息失败: {e}，将尝试更新")
                return existing_actual_id, problem_id_to_use, None
        
        # ============ 题目不存在，创建新题目 ============
        logger.info(f"[{original_id}] SHSOJ 上不存在 problemId={problem_id_to_use}，创建新题目...")
        create_result = case_module.create_problem(auth, problem_data, file_dir)
        
        # 安全检查创建结果
        if not create_result:
            raise RuntimeError("创建题目失败：返回结果为空")
        
        # 从创建结果中获取新题目的ID
        data = create_result.get("data")
        if not data:
            raise RuntimeError(f"创建题目失败：响应中缺少data字段: {create_result}")
        
        created_problem = data.get("problem")
        if not created_problem:
            raise RuntimeError(f"创建题目失败：data中缺少problem字段: {create_result}")
        
        actual_id = created_problem.get("id")
        problem_id_str = created_problem.get("problemId", str(actual_id) if actual_id else "")
        
        if not actual_id:
            raise RuntimeError(f"创建题目失败，未返回ID: {create_result}")
        
        # 返回ID和上传结果
        upload_result_with_dir = {"fileListDir": file_dir, "dir": file_dir, "fileList": file_list}
        return actual_id, problem_id_str, upload_result_with_dir
