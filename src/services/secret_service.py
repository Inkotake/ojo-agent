# -*- coding: utf-8 -*-
"""
敏感信息加密服务 v9.0

加密对象：API Key、密码、Cookie、Token 等敏感信息
使用 Fernet 对称加密（AES-128-CBC + HMAC）
"""

import os
import threading
from typing import Optional
from loguru import logger

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    raise ImportError("请安装 cryptography: pip install cryptography")


class SecretService:
    """
    敏感信息加密服务（单例）
    
    特性：
    1. 透明加解密
    2. 密钥安全存储（数据库/环境变量）
    3. 旧数据兼容（明文数据自动识别）
    """
    
    _instance: Optional['SecretService'] = None
    _lock = threading.Lock()
    
    # 敏感字段名称（用于自动识别需加密的字段）
    SENSITIVE_KEYS = frozenset([
        'password', 'api_key', 'token', 'cookie', 'sid', 'secret',
        'deepseek_api_key', 'gemini_api_key', 'openai_api_key',
        'deepseek_api_key_siliconflow', 'sid_sig'
    ])
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db=None):
        if self._initialized:
            return
        
        self._db = db
        self._cipher: Optional[Fernet] = None
        self._key: Optional[str] = None
        self._initialized = True
        
        logger.info("[SecretService] 加密服务初始化完成")
    
    def set_database(self, db):
        """设置数据库实例"""
        self._db = db
    
    @property
    def db(self):
        """获取数据库实例（懒加载）"""
        if self._db is None:
            from core.database import get_database
            self._db = get_database()
        return self._db
    
    @property
    def cipher(self) -> Fernet:
        """获取加密器（懒加载）"""
        if self._cipher is not None:
            return self._cipher
        
        # 1. 从数据库获取密钥
        try:
            self._key = self.db.get_system_config("encryption_key")
            if self._key:
                self._cipher = Fernet(self._key.encode())
                return self._cipher
        except Exception as e:
            logger.debug(f"从数据库获取加密密钥失败: {e}")
        
        # 2. 从环境变量获取
        self._key = os.getenv("OJO_ENCRYPTION_KEY")
        if self._key:
            try:
                self._cipher = Fernet(self._key.encode())
                return self._cipher
            except Exception:
                logger.warning("环境变量中的加密密钥无效，将生成新密钥")
        
        # 3. 生成新密钥
        self._key = Fernet.generate_key().decode()
        self._cipher = Fernet(self._key.encode())
        
        # 存储到数据库
        try:
            self.db.set_system_config("encryption_key", self._key)
            logger.info("[SecretService] 生成新的加密密钥并存储到数据库")
        except Exception as e:
            logger.warning(f"无法存储加密密钥: {e}")
        
        return self._cipher
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串
        
        Args:
            plaintext: 明文字符串
            
        Returns:
            加密后的字符串（Base64编码）
        """
        if not plaintext:
            return ""
        
        try:
            encrypted = self.cipher.encrypt(plaintext.encode('utf-8'))
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"加密失败: {e}")
            return plaintext  # 失败时返回原文（避免数据丢失）
    
    def decrypt(self, ciphertext: str) -> str:
        """
        解密字符串
        
        Args:
            ciphertext: 密文字符串
            
        Returns:
            解密后的明文
        """
        if not ciphertext:
            return ""
        
        try:
            decrypted = self.cipher.decrypt(ciphertext.encode('utf-8'))
            return decrypted.decode('utf-8')
        except InvalidToken:
            # 可能是旧的明文数据，直接返回
            logger.debug("解密失败（可能是明文数据），返回原值")
            return ciphertext
        except Exception as e:
            logger.warning(f"解密失败: {e}")
            return ciphertext  # 失败时返回原文
    
    def is_encrypted(self, value: str) -> bool:
        """检查值是否已加密"""
        if not value:
            return False
        
        try:
            # Fernet 加密的数据以 gAAAAA 开头
            return value.startswith('gAAAAA')
        except Exception:
            return False
    
    def encrypt_dict(self, data: dict, keys: set = None) -> dict:
        """
        加密字典中的敏感字段
        
        Args:
            data: 原始字典
            keys: 要加密的字段名集合（默认使用 SENSITIVE_KEYS）
            
        Returns:
            加密后的字典（副本）
        """
        if not data:
            return data
        
        keys = keys or self.SENSITIVE_KEYS
        result = data.copy()
        
        for key, value in result.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in keys):
                if value and isinstance(value, str) and not self.is_encrypted(value):
                    result[key] = self.encrypt(value)
        
        return result
    
    def decrypt_dict(self, data: dict, keys: set = None) -> dict:
        """
        解密字典中的敏感字段
        
        Args:
            data: 加密的字典
            keys: 要解密的字段名集合（默认使用 SENSITIVE_KEYS）
            
        Returns:
            解密后的字典（副本）
        """
        if not data:
            return data
        
        keys = keys or self.SENSITIVE_KEYS
        result = data.copy()
        
        for key, value in result.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in keys):
                if value and isinstance(value, str) and self.is_encrypted(value):
                    result[key] = self.decrypt(value)
        
        return result
    
    def export_key(self) -> str:
        """导出加密密钥（用于备份）"""
        _ = self.cipher  # 确保密钥已初始化
        return self._key
    
    def import_key(self, key: str) -> bool:
        """导入加密密钥"""
        try:
            # 验证密钥有效性
            test_cipher = Fernet(key.encode())
            test_cipher.encrypt(b"test")
            
            # 更新密钥
            self._key = key
            self._cipher = test_cipher
            
            # 存储到数据库
            self.db.set_system_config("encryption_key", key)
            logger.info("[SecretService] 导入新的加密密钥")
            
            return True
        except Exception as e:
            logger.error(f"导入密钥失败: {e}")
            return False


# ==================== 全局访问函数 ====================

_secret_service: Optional[SecretService] = None


def get_secret_service() -> SecretService:
    """获取加密服务实例"""
    global _secret_service
    if _secret_service is None:
        _secret_service = SecretService()
    return _secret_service


def encrypt_sensitive(value: str) -> str:
    """加密敏感值（便捷函数）"""
    return get_secret_service().encrypt(value)


def decrypt_sensitive(value: str) -> str:
    """解密敏感值（便捷函数）"""
    return get_secret_service().decrypt(value)
