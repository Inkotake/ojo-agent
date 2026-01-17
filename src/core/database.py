# -*- coding: utf-8 -*-
"""
SQLite数据库模型和管理
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
from loguru import logger


class Database:
    """SQLite数据库管理器"""
    
    def __init__(self, db_path: str = None):
        # 优先使用环境变量，其次使用 /app/data，最后使用当前目录
        if db_path is None:
            import os
            db_path = os.getenv("OJO_DB_PATH")
            if not db_path:
                # Docker 环境下使用持久化目录
                data_dir = Path("/app/data")
                if data_dir.exists():
                    db_path = str(data_dir / "ojo.db")
                else:
                    db_path = "ojo.db"
        
        self.db_path = Path(db_path)
        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._insert_default_users()
        
        # 首次运行时尝试从 config.json 迁移配置到数据库
        # 迁移完成后，运行时完全依赖数据库，不再读取 config.json
        config_path = Path("config.json")
        if config_path.exists():
            try:
                self.migrate_config_from_file(config_path)
            except Exception as e:
                logger.warning(f"配置迁移失败，将使用默认配置: {e}")
    
    def _create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()
        
        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        
        # 用户配置表（偏好设置）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                cookie TEXT,
                token TEXT,
                auto_download BOOLEAN DEFAULT 1,
                keep_cache BOOLEAN DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, platform)
            )
        """)
        
        # 用户适配器配置表（每个用户独立的适配器配置）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_adapter_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                adapter_name TEXT NOT NULL,
                config_data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, adapter_name)
            )
        """)
        
        # 用户模块适配器设置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_module_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                settings_data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 任务表（每条记录=一个用户的一个任务）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                problem_id TEXT NOT NULL,
                status INTEGER DEFAULT 0,
                progress INTEGER DEFAULT 0,
                stage TEXT DEFAULT 'pending',
                source_oj TEXT,
                target_oj TEXT,
                uploaded_url TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 系统配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_configs (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 活动日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                target TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 任务队列表 (持久化队列，崩溃恢复)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                problem_ids TEXT NOT NULL,
                config TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                worker_id TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 任务进度表 (细粒度进度跟踪)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                problem_id TEXT NOT NULL,
                module TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                UNIQUE(task_id, problem_id, module)
            )
        """)
        
        # ============= 索引优化 =============
        # 任务表索引 - 按用户查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_id 
            ON tasks(user_id)
        """)
        
        # 任务表索引 - 按状态查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status 
            ON tasks(status)
        """)
        
        # 任务表索引 - 按创建时间排序
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_created_at 
            ON tasks(created_at DESC)
        """)
        
        # 任务表复合索引 - 用户+状态组合查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_status 
            ON tasks(user_id, status)
        """)
        
        # 活动日志索引 - 按用户查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_user_id 
            ON activity_logs(user_id)
        """)
        
        # 活动日志索引 - 按时间排序
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_created_at 
            ON activity_logs(created_at DESC)
        """)
        
        # 用户配置索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_configs_user_id 
            ON user_configs(user_id)
        """)
        
        # 用户适配器配置索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_adapter_configs_user_id 
            ON user_adapter_configs(user_id)
        """)
        
        # 邀请码表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invite_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                used_by INTEGER,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (used_by) REFERENCES users(id)
            )
        """)
        
        # 邀请码索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invite_codes_code 
            ON invite_codes(code)
        """)
        
        # ============= 项目信息模块表 =============
        # 更新日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS changelogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                type TEXT DEFAULT 'feature',
                is_published BOOLEAN DEFAULT 0,
                publish_date TIMESTAMP,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        
        # 更新日志索引 - 按发布状态和日期查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_changelogs_published 
            ON changelogs(is_published, publish_date DESC)
        """)
        
        # 用户已读更新日志记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_changelog_reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                last_read_changelog_id INTEGER NOT NULL,
                read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 用户反馈表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                admin_reply TEXT,
                admin_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (admin_id) REFERENCES users(id)
            )
        """)
        
        # 反馈表索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedbacks_status 
            ON feedbacks(status, created_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedbacks_user 
            ON feedbacks(user_id)
        """)
        
        self.conn.commit()
        logger.info("数据库表和索引创建完成")
        
        # 运行数据库迁移
        self._run_migrations()
    
    def _run_migrations(self):
        """运行数据库迁移"""
        cursor = self.conn.cursor()
        
        # 迁移 2: 添加 source_oj 和 uploaded_url 字段
        try:
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'source_oj' not in columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN source_oj TEXT")
                logger.info("添加 source_oj 字段到 tasks 表")
            
            if 'uploaded_url' not in columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN uploaded_url TEXT")
                logger.info("添加 uploaded_url 字段到 tasks 表")
            
            self.conn.commit()
        except Exception as e:
            logger.debug(f"迁移 source_oj/uploaded_url 字段跳过: {e}")
        
        # 迁移: 添加 target_oj 字段（如果不存在）
        try:
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'target_oj' not in columns:
                cursor.execute("ALTER TABLE tasks ADD COLUMN target_oj TEXT")
                logger.info("添加 target_oj 字段到 tasks 表")
                self.conn.commit()
        except Exception as e:
            logger.debug(f"迁移 target_oj 字段跳过: {e}")
    
    def _insert_default_users(self):
        """插入默认用户（密码使用bcrypt加密）"""
        cursor = self.conn.cursor()
        
        # 检查是否已有用户
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] > 0:
            return
        
        # 导入认证模块（延迟导入避免循环依赖）
        try:
            import sys
            from pathlib import Path
            # 确保可以导入auth模块
            src_dir = Path(__file__).parent.parent
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            from api.auth import hash_password
        except ImportError as e:
            # 如果导入失败，记录错误但不阻塞数据库初始化
            logger.warning(f"无法导入auth模块，将尝试直接使用bcrypt: {e}")
            try:
                import bcrypt
                hash_password = lambda p: bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            except ImportError:
                logger.error("bcrypt未安装，默认用户密码将使用明文（不安全）！请安装: pip install bcrypt")
                hash_password = lambda p: p
        
        # 插入默认管理员（从环境变量读取或生成随机密码）
        import os
        default_password = os.environ.get("OJO_ADMIN_PASSWORD", "")
        if not default_password:
            import secrets
            default_password = secrets.token_urlsafe(16)
            logger.warning(f"=== 首次运行：默认管理员密码已生成 ===")
            logger.warning(f"用户名: inkotake")
            logger.warning(f"密码: {default_password}")
            logger.warning(f"请妥善保管此密码，或设置环境变量 OJO_ADMIN_PASSWORD")
            logger.warning(f"=" * 50)
        
        hashed_password = hash_password(default_password)
        cursor.execute("""
            INSERT INTO users (username, password, email, role)
            VALUES (?, ?, ?, ?)
        """, ("inkotake", hashed_password, "inkotake@ojo.local", "admin"))
        
        self.conn.commit()
        logger.info("默认管理员用户创建完成（密码已加密）")
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_last_login(self, user_id: int):
        """更新最后登录时间"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
        """, (user_id,))
        self.conn.commit()
    
    def get_all_users(self) -> List[Dict]:
        """获取所有用户"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, username, email, role, status, last_login FROM users")
        return [dict(row) for row in cursor.fetchall()]
    
    def create_task(self, user_id: int, problem_id: str, source_oj: str = None, target_oj: str = None) -> int:
        """创建任务，返回任务ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (user_id, problem_id, source_oj, target_oj, status, progress, stage)
            VALUES (?, ?, ?, ?, 0, 0, 'pending')
        """, (user_id, problem_id, source_oj, target_oj))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_task(self, task_id: int, status: int = None, progress: int = None, 
                    stage: str = None, error_message: str = None, uploaded_url: str = None):
        """更新任务状态
        
        Args:
            task_id: 任务ID (数据库主键)
            其他参数为要更新的字段
        """
        cursor = self.conn.cursor()
        updates = []
        params = []
        
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if stage is not None:
            updates.append("stage = ?")
            params.append(stage)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if uploaded_url is not None:
            updates.append("uploaded_url = ?")
            params.append(uploaded_url)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(task_id)
            sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            self.conn.commit()
    
    def get_user_tasks(self, user_id: int, limit: int = 50) -> List[Dict]:
        """获取用户的任务"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_tasks(self, limit: int = 100) -> List[Dict]:
        """获取所有任务（管理员）"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT t.*, u.username 
            FROM tasks t
            JOIN users u ON t.user_id = u.id
            ORDER BY t.created_at DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_user_config(self, user_id: int, platform: str = None) -> Dict:
        """获取用户配置"""
        cursor = self.conn.cursor()
        if platform:
            cursor.execute("""
                SELECT * FROM user_configs WHERE user_id = ? AND platform = ?
            """, (user_id, platform))
            row = cursor.fetchone()
            return dict(row) if row else {}
        else:
            cursor.execute("""
                SELECT * FROM user_configs WHERE user_id = ?
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def save_user_config(self, user_id: int, platform: str, cookie: str = None, 
                        token: str = None, auto_download: bool = None, keep_cache: bool = None):
        """保存用户配置"""
        cursor = self.conn.cursor()
        
        # 检查是否存在
        cursor.execute("""
            SELECT id FROM user_configs WHERE user_id = ? AND platform = ?
        """, (user_id, platform))
        
        if cursor.fetchone():
            # 更新
            updates = []
            params = []
            if cookie is not None:
                updates.append("cookie = ?")
                params.append(cookie)
            if token is not None:
                updates.append("token = ?")
                params.append(token)
            if auto_download is not None:
                updates.append("auto_download = ?")
                params.append(auto_download)
            if keep_cache is not None:
                updates.append("keep_cache = ?")
                params.append(keep_cache)
            
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.extend([user_id, platform])
                sql = f"UPDATE user_configs SET {', '.join(updates)} WHERE user_id = ? AND platform = ?"
                cursor.execute(sql, params)
        else:
            # 插入
            cursor.execute("""
                INSERT INTO user_configs (user_id, platform, cookie, token, auto_download, keep_cache)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, platform, cookie, token, 
                  auto_download if auto_download is not None else True,
                  keep_cache if keep_cache is not None else True))
        
        self.conn.commit()
    
    def log_activity(self, user_id: int, action: str, target: str = None, details: Dict = None):
        """记录活动日志"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (user_id, action, target, details)
            VALUES (?, ?, ?, ?)
        """, (user_id, action, target, json.dumps(details) if details else None))
        self.conn.commit()
    
    def get_recent_activities(self, limit: int = 50) -> List[Dict]:
        """获取最近的活动"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT a.*, u.username 
            FROM activity_logs a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 用户适配器配置管理 ====================
    
    def get_user_adapter_config(self, user_id: int, adapter_name: str) -> Dict:
        """获取用户的适配器配置"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT config_data FROM user_adapter_configs 
            WHERE user_id = ? AND adapter_name = ?
        """, (user_id, adapter_name))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except:
                return {}
        return {}
    
    def get_all_user_adapter_configs(self, user_id: int) -> Dict[str, Dict]:
        """获取用户的所有适配器配置"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT adapter_name, config_data FROM user_adapter_configs 
            WHERE user_id = ?
        """, (user_id,))
        configs = {}
        for row in cursor.fetchall():
            try:
                configs[row[0]] = json.loads(row[1])
            except:
                configs[row[0]] = {}
        return configs
    
    def save_user_adapter_config(self, user_id: int, adapter_name: str, config: Dict):
        """保存用户的适配器配置"""
        cursor = self.conn.cursor()
        config_str = json.dumps(config, ensure_ascii=False)
        cursor.execute("""
            INSERT OR REPLACE INTO user_adapter_configs (user_id, adapter_name, config_data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, adapter_name, config_str))
        self.conn.commit()
    
    def get_user_module_settings(self, user_id: int) -> Dict:
        """获取用户的模块适配器设置"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT settings_data FROM user_module_settings WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except:
                return {}
        # 返回默认设置
        return {
            "fetch": {"mode": "auto"},
            "upload": {"mode": "manual", "adapter": "shsoj"},
            "submit": {"mode": "manual", "adapter": "shsoj"}
        }
    
    def save_user_module_settings(self, user_id: int, settings: Dict):
        """保存用户的模块适配器设置"""
        cursor = self.conn.cursor()
        settings_str = json.dumps(settings, ensure_ascii=False)
        cursor.execute("""
            INSERT OR REPLACE INTO user_module_settings (user_id, settings_data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, settings_str))
        self.conn.commit()
    
    # ==================== 系统配置管理 ====================
    
    def get_system_config(self, key: str, default: Any = None) -> Any:
        """获取系统配置"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM system_configs WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])  # JSON解码
            except:
                return row[0]  # 如果是纯字符串
        return default
    
    def set_system_config(self, key: str, value: Any):
        """设置系统配置"""
        cursor = self.conn.cursor()
        # 值存储为JSON字符串
        value_str = json.dumps(value) if not isinstance(value, str) else value
        cursor.execute("""
            INSERT OR REPLACE INTO system_configs (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value_str))
        self.conn.commit()
    
    def get_all_system_configs(self) -> Dict[str, Any]:
        """获取所有系统配置"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM system_configs")
        configs = {}
        for row in cursor.fetchall():
            try:
                configs[row[0]] = json.loads(row[1])
            except:
                configs[row[0]] = row[1]
        return configs
    
    def migrate_config_from_file(self, config_path: Path):
        """从 config.json 文件迁移配置到数据库
        
        迁移策略：
        1. 普通配置存入 app_config（JSON 格式）
        2. API Key 加密后存入独立 key（安全存储）
        3. 设置 config_migrated 标记避免重复迁移
        """
        import secrets
        
        # 检查是否已经迁移过
        existing = self.get_system_config("config_migrated", False)
        if existing:
            logger.info("配置已从文件迁移到数据库，跳过迁移")
            return
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}，跳过迁移")
            return
        
        try:
            # 读取config.json
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 生成JWT密钥（如果还没有）
            jwt_key = self.get_system_config("jwt_secret_key")
            if not jwt_key:
                jwt_key = secrets.token_urlsafe(32)
                self.set_system_config("jwt_secret_key", jwt_key)
                logger.info("JWT密钥已生成并存储到数据库")
            
            # API Key 字段列表（需要加密存储）
            api_key_fields = [
                'deepseek_api_key',
                'deepseek_api_key_siliconflow',
                'openai_api_key',
            ]
            
            # 分离 API Key 和普通配置
            api_keys = {}
            app_config = {}
            
            for key, value in config_data.items():
                if key in api_key_fields and value:
                    api_keys[key] = value
                else:
                    app_config[key] = value
            
            # 存储普通配置到 app_config
            self.set_system_config("app_config", app_config)
            
            # 加密存储 API Key
            if api_keys:
                try:
                    from services.secret_service import get_secret_service
                    secret_service = get_secret_service()
                    
                    for key, value in api_keys.items():
                        encrypted = secret_service.encrypt(value)
                        self.set_system_config(key, encrypted)
                        logger.info(f"API Key {key} 已加密迁移到数据库")
                except Exception as e:
                    logger.warning(f"API Key 加密迁移失败: {e}")
            
            # 标记已迁移
            self.set_system_config("config_migrated", True)
            
            logger.info("配置已成功从文件迁移到数据库")
            
        except Exception as e:
            logger.error(f"配置迁移失败: {e}")
            raise
    
    # ============= 任务队列方法 =============
    
    def enqueue_task(self, task_id: str, user_id: int, problem_ids: list, 
                     config: dict, priority: int = 0) -> int:
        """添加任务到队列"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO task_queue (task_id, user_id, problem_ids, config, priority, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (task_id, user_id, json.dumps(problem_ids), json.dumps(config), priority))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_pending_tasks(self, limit: int = 10) -> List[Dict]:
        """获取待执行的任务（按优先级和时间排序）"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM task_queue 
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def claim_task(self, task_id: str, worker_id: str) -> bool:
        """认领任务（原子操作）"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE task_queue 
            SET status = 'running', worker_id = ?, started_at = CURRENT_TIMESTAMP
            WHERE task_id = ? AND status = 'pending'
        """, (worker_id, task_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def complete_task_queue(self, task_id: str, success: bool, error_message: str = None):
        """完成队列任务"""
        cursor = self.conn.cursor()
        status = 'completed' if success else 'failed'
        cursor.execute("""
            UPDATE task_queue 
            SET status = ?, completed_at = CURRENT_TIMESTAMP, error_message = ?
            WHERE task_id = ?
        """, (status, error_message, task_id))
        self.conn.commit()
    
    def retry_task_queue(self, task_id: str, error_message: str = None) -> bool:
        """重试失败的任务"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE task_queue 
            SET status = 'pending', retry_count = retry_count + 1, 
                error_message = ?, worker_id = NULL, started_at = NULL
            WHERE task_id = ? AND retry_count < max_retries
        """, (error_message, task_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_queue_stats(self) -> Dict:
        """获取队列统计信息"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM task_queue GROUP BY status
        """)
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("SELECT COUNT(*) FROM task_queue")
        stats['total'] = cursor.fetchone()[0]
        
        return stats
    
    def get_user_queue_count(self, user_id: int) -> int:
        """获取用户队列中的任务数"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM task_queue 
            WHERE user_id = ? AND status IN ('pending', 'running')
        """, (user_id,))
        return cursor.fetchone()[0]
    
    def cleanup_stale_tasks(self, timeout_seconds: int = 600):
        """清理超时的任务（标记为失败）"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE task_queue 
            SET status = 'failed', error_message = 'Task timeout'
            WHERE status = 'running' 
            AND started_at < datetime('now', ? || ' seconds')
        """, (-timeout_seconds,))
        cleaned = cursor.rowcount
        self.conn.commit()
        if cleaned > 0:
            logger.info(f"清理了 {cleaned} 个超时任务")
        return cleaned
    
    def recover_interrupted_tasks(self):
        """恢复中断的任务（系统重启后调用）"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE task_queue 
            SET status = 'pending', worker_id = NULL, started_at = NULL
            WHERE status = 'running'
        """)
        recovered = cursor.rowcount
        self.conn.commit()
        if recovered > 0:
            logger.info(f"恢复了 {recovered} 个中断的任务")
        return recovered
    
    # ============= 任务进度方法 =============
    
    def update_task_progress(self, task_id: str, problem_id: str, module: str,
                             status: str = None, progress: int = None, 
                             message: str = None, error_message: str = None):
        """更新任务进度"""
        cursor = self.conn.cursor()
        
        # 先尝试插入
        try:
            cursor.execute("""
                INSERT INTO task_progress (task_id, problem_id, module, status, progress, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (task_id, problem_id, module, status or 'pending', progress or 0, message))
        except sqlite3.IntegrityError:
            # 已存在，更新
            updates = []
            params = []
            if status:
                updates.append("status = ?")
                params.append(status)
            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            if message:
                updates.append("message = ?")
                params.append(message)
            if error_message:
                updates.append("error_message = ?")
                params.append(error_message)
            if status == 'running':
                updates.append("started_at = CURRENT_TIMESTAMP")
            if status in ('completed', 'failed'):
                updates.append("completed_at = CURRENT_TIMESTAMP")
            
            if updates:
                params.extend([task_id, problem_id, module])
                cursor.execute(f"""
                    UPDATE task_progress SET {', '.join(updates)}
                    WHERE task_id = ? AND problem_id = ? AND module = ?
                """, params)
        
        self.conn.commit()
    
    def get_task_progress(self, task_id: str) -> List[Dict]:
        """获取任务的所有进度"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM task_progress WHERE task_id = ?
            ORDER BY problem_id, module
        """, (task_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 邀请码管理 ====================
    
    def create_invite_code(self, code: str, created_by: int, note: str = None, expires_at: str = None) -> int:
        """创建邀请码"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO invite_codes (code, created_by, note, expires_at)
            VALUES (?, ?, ?, ?)
        """, (code, created_by, note, expires_at))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_invite_code(self, code: str) -> Optional[Dict]:
        """获取邀请码信息"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM invite_codes WHERE code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def use_invite_code(self, code: str, user_id: int) -> bool:
        """使用邀请码"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE invite_codes 
            SET used_by = ?, used_at = CURRENT_TIMESTAMP
            WHERE code = ? AND used_by IS NULL
        """, (user_id, code))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_all_invite_codes(self, created_by: int = None) -> List[Dict]:
        """获取所有邀请码（管理员）"""
        cursor = self.conn.cursor()
        if created_by:
            cursor.execute("""
                SELECT ic.*, 
                       u1.username as creator_name,
                       u2.username as used_by_name
                FROM invite_codes ic
                LEFT JOIN users u1 ON ic.created_by = u1.id
                LEFT JOIN users u2 ON ic.used_by = u2.id
                WHERE ic.created_by = ?
                ORDER BY ic.created_at DESC
            """, (created_by,))
        else:
            cursor.execute("""
                SELECT ic.*, 
                       u1.username as creator_name,
                       u2.username as used_by_name
                FROM invite_codes ic
                LEFT JOIN users u1 ON ic.created_by = u1.id
                LEFT JOIN users u2 ON ic.used_by = u2.id
                ORDER BY ic.created_at DESC
            """)
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_invite_code(self, code_id: int) -> bool:
        """删除邀请码"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM invite_codes WHERE id = ?", (code_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def create_user(self, username: str, password: str, role: str = 'user') -> Optional[int]:
        """创建用户"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password, role, status)
                VALUES (?, ?, ?, 'active')
            """, (username, password, role))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None  # 用户名已存在
    
    def update_user_password(self, user_id: int, new_password: str) -> bool:
        """更新用户密码"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET password = ? WHERE id = ?
        """, (new_password, user_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ==================== 更新日志管理 ====================
    
    def create_changelog(self, version: str, title: str, content: str, 
                         type: str, created_by: int, is_published: bool = False) -> int:
        """创建更新日志"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO changelogs (version, title, content, type, created_by, is_published)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (version, title, content, type, created_by, is_published))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_changelog(self, changelog_id: int, version: str = None, title: str = None,
                         content: str = None, type: str = None, is_published: bool = None) -> bool:
        """更新更新日志"""
        cursor = self.conn.cursor()
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        
        if version is not None:
            updates.append("version = ?")
            params.append(version)
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if type is not None:
            updates.append("type = ?")
            params.append(type)
        if is_published is not None:
            updates.append("is_published = ?")
            params.append(is_published)
            if is_published:
                updates.append("publish_date = CURRENT_TIMESTAMP")
        
        params.append(changelog_id)
        cursor.execute(f"UPDATE changelogs SET {', '.join(updates)} WHERE id = ?", params)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_changelog(self, changelog_id: int) -> bool:
        """删除更新日志"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM changelogs WHERE id = ?", (changelog_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_changelogs(self, include_drafts: bool = False, limit: int = 20) -> List[Dict]:
        """获取更新日志列表"""
        cursor = self.conn.cursor()
        if include_drafts:
            cursor.execute("""
                SELECT c.*, u.username as author_name
                FROM changelogs c
                LEFT JOIN users u ON c.created_by = u.id
                ORDER BY c.publish_date DESC NULLS LAST, c.created_at DESC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT c.*, u.username as author_name
                FROM changelogs c
                LEFT JOIN users u ON c.created_by = u.id
                WHERE c.is_published = 1
                ORDER BY c.publish_date DESC
                LIMIT ?
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_changelog_by_id(self, changelog_id: int) -> Optional[Dict]:
        """根据ID获取更新日志"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, u.username as author_name
            FROM changelogs c
            LEFT JOIN users u ON c.created_by = u.id
            WHERE c.id = ?
        """, (changelog_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_latest_published_changelog_id(self) -> Optional[int]:
        """获取最新已发布的更新日志ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id FROM changelogs 
            WHERE is_published = 1 
            ORDER BY publish_date DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        return row[0] if row else None
    
    def get_user_last_read_changelog_id(self, user_id: int) -> Optional[int]:
        """获取用户最后已读的更新日志ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT last_read_changelog_id FROM user_changelog_reads WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    
    def mark_changelog_read(self, user_id: int, changelog_id: int) -> bool:
        """标记更新日志为已读"""
        cursor = self.conn.cursor()
        # UPSERT: 更新或插入
        cursor.execute("""
            INSERT INTO user_changelog_reads (user_id, last_read_changelog_id, read_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET 
                last_read_changelog_id = excluded.last_read_changelog_id,
                read_at = CURRENT_TIMESTAMP
        """, (user_id, changelog_id))
        self.conn.commit()
        return True
    
    def get_unread_changelog_count(self, user_id: int) -> int:
        """获取未读更新日志数量"""
        last_read_id = self.get_user_last_read_changelog_id(user_id) or 0
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM changelogs 
            WHERE is_published = 1 AND id > ?
        """, (last_read_id,))
        return cursor.fetchone()[0]
    
    # ==================== 用户反馈管理 ====================
    
    def create_feedback(self, user_id: int, type: str, title: str, content: str) -> int:
        """创建用户反馈"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO feedbacks (user_id, type, title, content)
            VALUES (?, ?, ?, ?)
        """, (user_id, type, title, content))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_feedback(self, feedback_id: int, status: str = None, priority: int = None,
                        admin_reply: str = None, admin_id: int = None) -> bool:
        """更新反馈（管理员回复）"""
        cursor = self.conn.cursor()
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        if admin_reply is not None:
            updates.append("admin_reply = ?")
            params.append(admin_reply)
        if admin_id is not None:
            updates.append("admin_id = ?")
            params.append(admin_id)
        
        params.append(feedback_id)
        cursor.execute(f"UPDATE feedbacks SET {', '.join(updates)} WHERE id = ?", params)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_feedbacks(self, user_id: int = None, status: str = None, 
                      type: str = None, limit: int = 50) -> List[Dict]:
        """获取反馈列表"""
        cursor = self.conn.cursor()
        conditions = []
        params = []
        
        if user_id is not None:
            conditions.append("f.user_id = ?")
            params.append(user_id)
        if status is not None:
            conditions.append("f.status = ?")
            params.append(status)
        if type is not None:
            conditions.append("f.type = ?")
            params.append(type)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        
        cursor.execute(f"""
            SELECT f.*, u.username as author_name, a.username as admin_name
            FROM feedbacks f
            LEFT JOIN users u ON f.user_id = u.id
            LEFT JOIN users a ON f.admin_id = a.id
            {where_clause}
            ORDER BY f.priority DESC, f.created_at DESC
            LIMIT ?
        """, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_feedback_by_id(self, feedback_id: int) -> Optional[Dict]:
        """根据ID获取反馈"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT f.*, u.username as author_name, a.username as admin_name
            FROM feedbacks f
            LEFT JOIN users u ON f.user_id = u.id
            LEFT JOIN users a ON f.admin_id = a.id
            WHERE f.id = ?
        """, (feedback_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def delete_feedback(self, feedback_id: int) -> bool:
        """删除反馈"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM feedbacks WHERE id = ?", (feedback_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


# 全局数据库实例
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """获取全局数据库实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
