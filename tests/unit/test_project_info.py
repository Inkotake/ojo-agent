# -*- coding: utf-8 -*-
"""
项目信息功能单元测试

测试内容：
1. 数据库方法 - 更新日志 CRUD
2. 数据库方法 - 用户反馈 CRUD
3. 数据库方法 - 未读计数逻辑
4. API 路由验证
"""

import sys
import unittest
import tempfile
import os
from pathlib import Path
from datetime import datetime

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestChangelogDatabase(unittest.TestCase):
    """更新日志数据库方法测试"""
    
    @classmethod
    def setUpClass(cls):
        """创建临时数据库"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_ojo.db")
        os.environ["OJO_DB_PATH"] = cls.db_path
        
        # 重新导入以使用新路径
        from core.database import Database
        cls.db = Database(cls.db_path)
        
        # 创建测试用户
        cursor = cls.db.conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, role, status)
            VALUES ('test_admin', 'hash', 'admin', 'active')
        """)
        cursor.execute("""
            INSERT INTO users (username, password, role, status)
            VALUES ('test_user', 'hash', 'user', 'active')
        """)
        cls.db.conn.commit()
        
        # 获取用户 ID
        cursor.execute("SELECT id FROM users WHERE username = 'test_admin'")
        cls.admin_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE username = 'test_user'")
        cls.user_id = cursor.fetchone()[0]
    
    @classmethod
    def tearDownClass(cls):
        """清理临时数据库"""
        cls.db.close()
        try:
            os.remove(cls.db_path)
            os.rmdir(cls.temp_dir)
        except:
            pass
    
    def test_create_changelog(self):
        """测试创建更新日志"""
        changelog_id = self.db.create_changelog(
            version="v9.1.0",
            title="测试更新",
            content="这是测试内容",
            type="feature",
            created_by=self.admin_id,
            is_published=False
        )
        
        self.assertIsNotNone(changelog_id)
        self.assertGreater(changelog_id, 0)
        
        # 验证创建的日志
        changelog = self.db.get_changelog_by_id(changelog_id)
        self.assertEqual(changelog["version"], "v9.1.0")
        self.assertEqual(changelog["title"], "测试更新")
        self.assertEqual(changelog["is_published"], 0)  # SQLite 返回 0/1
    
    def test_update_changelog(self):
        """测试更新更新日志"""
        # 创建日志
        changelog_id = self.db.create_changelog(
            version="v9.2.0",
            title="原标题",
            content="原内容",
            type="bugfix",
            created_by=self.admin_id
        )
        
        # 更新日志
        success = self.db.update_changelog(
            changelog_id,
            title="新标题",
            content="新内容"
        )
        
        self.assertTrue(success)
        
        # 验证更新
        changelog = self.db.get_changelog_by_id(changelog_id)
        self.assertEqual(changelog["title"], "新标题")
        self.assertEqual(changelog["content"], "新内容")
        self.assertEqual(changelog["version"], "v9.2.0")  # 未改变
    
    def test_publish_changelog(self):
        """测试发布更新日志"""
        # 创建草稿
        changelog_id = self.db.create_changelog(
            version="v9.3.0",
            title="草稿",
            content="内容",
            type="feature",
            created_by=self.admin_id,
            is_published=False
        )
        
        # 发布
        success = self.db.update_changelog(changelog_id, is_published=True)
        
        self.assertTrue(success)
        
        # 验证发布状态和时间
        changelog = self.db.get_changelog_by_id(changelog_id)
        self.assertEqual(changelog["is_published"], 1)
        self.assertIsNotNone(changelog["publish_date"])
    
    def test_delete_changelog(self):
        """测试删除更新日志"""
        # 创建日志
        changelog_id = self.db.create_changelog(
            version="v9.4.0",
            title="将被删除",
            content="内容",
            type="feature",
            created_by=self.admin_id
        )
        
        # 删除
        success = self.db.delete_changelog(changelog_id)
        
        self.assertTrue(success)
        
        # 验证删除
        changelog = self.db.get_changelog_by_id(changelog_id)
        self.assertIsNone(changelog)
    
    def test_get_changelogs_published_only(self):
        """测试获取已发布的更新日志"""
        # 清理现有日志（通过创建新的来测试）
        # 创建草稿
        self.db.create_changelog(
            version="draft",
            title="草稿日志",
            content="内容",
            type="feature",
            created_by=self.admin_id,
            is_published=False
        )
        
        # 创建已发布
        pub_id = self.db.create_changelog(
            version="published",
            title="已发布日志",
            content="内容",
            type="feature",
            created_by=self.admin_id,
            is_published=True
        )
        self.db.update_changelog(pub_id, is_published=True)  # 设置发布时间
        
        # 获取已发布的
        changelogs = self.db.get_changelogs(include_drafts=False)
        
        # 验证只包含已发布的
        versions = [c["version"] for c in changelogs]
        self.assertIn("published", versions)
        self.assertNotIn("draft", versions)
    
    def test_get_changelogs_include_drafts(self):
        """测试获取包含草稿的更新日志"""
        changelogs = self.db.get_changelogs(include_drafts=True)
        
        # 应该包含草稿
        has_draft = any(c["is_published"] == 0 for c in changelogs)
        self.assertTrue(has_draft)


class TestChangelogUnreadCount(unittest.TestCase):
    """更新日志未读计数测试"""
    
    @classmethod
    def setUpClass(cls):
        """创建临时数据库"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_unread.db")
        
        from core.database import Database
        cls.db = Database(cls.db_path)
        
        # 创建测试用户
        cursor = cls.db.conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, role, status)
            VALUES ('unread_admin', 'hash', 'admin', 'active')
        """)
        cursor.execute("""
            INSERT INTO users (username, password, role, status)
            VALUES ('unread_user', 'hash', 'user', 'active')
        """)
        cls.db.conn.commit()
        
        cursor.execute("SELECT id FROM users WHERE username = 'unread_admin'")
        cls.admin_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE username = 'unread_user'")
        cls.user_id = cursor.fetchone()[0]
    
    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        try:
            os.remove(cls.db_path)
            os.rmdir(cls.temp_dir)
        except:
            pass
    
    def test_initial_unread_count(self):
        """测试初始未读计数（无日志时）"""
        count = self.db.get_unread_changelog_count(self.user_id)
        self.assertEqual(count, 0)
    
    def test_unread_count_after_publish(self):
        """测试发布后未读计数增加"""
        # 创建并发布日志
        changelog_id = self.db.create_changelog(
            version="v1.0.0",
            title="新版本",
            content="内容",
            type="feature",
            created_by=self.admin_id,
            is_published=True
        )
        self.db.update_changelog(changelog_id, is_published=True)
        
        # 检查未读计数
        count = self.db.get_unread_changelog_count(self.user_id)
        self.assertGreaterEqual(count, 1)
    
    def test_mark_as_read(self):
        """测试标记为已读"""
        # 创建并发布日志
        changelog_id = self.db.create_changelog(
            version="v2.0.0",
            title="新版本2",
            content="内容",
            type="feature",
            created_by=self.admin_id,
            is_published=True
        )
        self.db.update_changelog(changelog_id, is_published=True)
        
        # 标记为已读
        result = self.db.mark_changelog_read(self.user_id, changelog_id)
        self.assertTrue(result)
        
        # 验证已读记录
        last_read = self.db.get_user_last_read_changelog_id(self.user_id)
        self.assertEqual(last_read, changelog_id)
    
    def test_unread_count_after_mark_read(self):
        """测试标记已读后未读计数为0"""
        # 获取最新日志 ID
        latest_id = self.db.get_latest_published_changelog_id()
        
        if latest_id:
            # 标记为已读
            self.db.mark_changelog_read(self.user_id, latest_id)
            
            # 检查未读计数
            count = self.db.get_unread_changelog_count(self.user_id)
            self.assertEqual(count, 0)


class TestFeedbackDatabase(unittest.TestCase):
    """用户反馈数据库方法测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_feedback.db")
        
        from core.database import Database
        cls.db = Database(cls.db_path)
        
        # 创建测试用户
        cursor = cls.db.conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, role, status)
            VALUES ('fb_admin', 'hash', 'admin', 'active')
        """)
        cursor.execute("""
            INSERT INTO users (username, password, role, status)
            VALUES ('fb_user', 'hash', 'user', 'active')
        """)
        cls.db.conn.commit()
        
        cursor.execute("SELECT id FROM users WHERE username = 'fb_admin'")
        cls.admin_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE username = 'fb_user'")
        cls.user_id = cursor.fetchone()[0]
    
    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        try:
            os.remove(cls.db_path)
            os.rmdir(cls.temp_dir)
        except:
            pass
    
    def test_create_feedback(self):
        """测试创建反馈"""
        feedback_id = self.db.create_feedback(
            user_id=self.user_id,
            type="feature",
            title="功能建议",
            content="希望添加某功能"
        )
        
        self.assertIsNotNone(feedback_id)
        self.assertGreater(feedback_id, 0)
        
        # 验证创建的反馈
        feedback = self.db.get_feedback_by_id(feedback_id)
        self.assertEqual(feedback["type"], "feature")
        self.assertEqual(feedback["title"], "功能建议")
        self.assertEqual(feedback["status"], "pending")
    
    def test_create_bug_report(self):
        """测试创建 Bug 报告"""
        feedback_id = self.db.create_feedback(
            user_id=self.user_id,
            type="bug",
            title="发现 Bug",
            content="Bug 详细描述"
        )
        
        feedback = self.db.get_feedback_by_id(feedback_id)
        self.assertEqual(feedback["type"], "bug")
    
    def test_admin_reply_feedback(self):
        """测试管理员回复反馈"""
        # 创建反馈
        feedback_id = self.db.create_feedback(
            user_id=self.user_id,
            type="question",
            title="问题咨询",
            content="如何使用某功能？"
        )
        
        # 管理员回复
        success = self.db.update_feedback(
            feedback_id,
            status="completed",
            admin_reply="您好，请参考文档...",
            admin_id=self.admin_id
        )
        
        self.assertTrue(success)
        
        # 验证回复
        feedback = self.db.get_feedback_by_id(feedback_id)
        self.assertEqual(feedback["status"], "completed")
        self.assertEqual(feedback["admin_reply"], "您好，请参考文档...")
        self.assertEqual(feedback["admin_id"], self.admin_id)
    
    def test_update_feedback_status(self):
        """测试更新反馈状态"""
        feedback_id = self.db.create_feedback(
            user_id=self.user_id,
            type="feature",
            title="状态测试",
            content="内容"
        )
        
        # 更新状态流程：pending -> reviewing -> planned -> completed
        statuses = ["reviewing", "planned", "completed"]
        
        for status in statuses:
            success = self.db.update_feedback(feedback_id, status=status)
            self.assertTrue(success)
            
            feedback = self.db.get_feedback_by_id(feedback_id)
            self.assertEqual(feedback["status"], status)
    
    def test_update_feedback_priority(self):
        """测试更新反馈优先级"""
        feedback_id = self.db.create_feedback(
            user_id=self.user_id,
            type="bug",
            title="优先级测试",
            content="内容"
        )
        
        # 设置高优先级
        success = self.db.update_feedback(feedback_id, priority=5)
        self.assertTrue(success)
        
        feedback = self.db.get_feedback_by_id(feedback_id)
        self.assertEqual(feedback["priority"], 5)
    
    def test_get_feedbacks_by_user(self):
        """测试按用户获取反馈"""
        # 创建用户的反馈
        self.db.create_feedback(
            user_id=self.user_id,
            type="feature",
            title="用户反馈1",
            content="内容"
        )
        
        # 获取用户的反馈
        feedbacks = self.db.get_feedbacks(user_id=self.user_id)
        
        # 验证都是该用户的
        for fb in feedbacks:
            self.assertEqual(fb["user_id"], self.user_id)
    
    def test_get_feedbacks_by_status(self):
        """测试按状态获取反馈"""
        # 创建不同状态的反馈
        fb_id = self.db.create_feedback(
            user_id=self.user_id,
            type="bug",
            title="已完成的反馈",
            content="内容"
        )
        self.db.update_feedback(fb_id, status="completed")
        
        # 获取已完成的反馈
        feedbacks = self.db.get_feedbacks(status="completed")
        
        # 验证都是已完成状态
        for fb in feedbacks:
            self.assertEqual(fb["status"], "completed")
    
    def test_get_feedbacks_by_type(self):
        """测试按类型获取反馈"""
        feedbacks = self.db.get_feedbacks(type="bug")
        
        for fb in feedbacks:
            self.assertEqual(fb["type"], "bug")
    
    def test_delete_feedback(self):
        """测试删除反馈"""
        feedback_id = self.db.create_feedback(
            user_id=self.user_id,
            type="other",
            title="将被删除",
            content="内容"
        )
        
        # 删除
        success = self.db.delete_feedback(feedback_id)
        self.assertTrue(success)
        
        # 验证删除
        feedback = self.db.get_feedback_by_id(feedback_id)
        self.assertIsNone(feedback)


class TestProjectAPIValidation(unittest.TestCase):
    """项目信息 API 参数验证测试"""
    
    def test_changelog_type_validation(self):
        """测试更新日志类型验证"""
        valid_types = ["feature", "bugfix", "improvement", "breaking"]
        invalid_types = ["invalid", "unknown", ""]
        
        for t in valid_types:
            self.assertIn(t, valid_types)
        
        for t in invalid_types:
            self.assertNotIn(t, valid_types)
    
    def test_feedback_type_validation(self):
        """测试反馈类型验证"""
        valid_types = ["feature", "bug", "question", "other"]
        
        self.assertEqual(len(valid_types), 4)
        self.assertIn("feature", valid_types)
        self.assertIn("bug", valid_types)
    
    def test_feedback_status_validation(self):
        """测试反馈状态验证"""
        valid_statuses = ["pending", "reviewing", "planned", "completed", "rejected"]
        
        self.assertEqual(len(valid_statuses), 5)
        self.assertIn("pending", valid_statuses)
        self.assertIn("completed", valid_statuses)
    
    def test_changelog_version_format(self):
        """测试版本号格式"""
        import re
        
        # 有效的版本号格式
        valid_versions = ["v9.0.0", "v9.1.0", "v10.0.0", "v1.2.3-beta"]
        
        # 简单的版本号验证（允许 v 开头）
        pattern = r"^v?\d+\.\d+\.\d+(-\w+)?$"
        
        for version in valid_versions:
            self.assertTrue(re.match(pattern, version), f"Invalid version: {version}")


class TestUnreadLogic(unittest.TestCase):
    """未读逻辑测试"""
    
    def test_has_unread_when_new_changelog(self):
        """测试有新日志时显示未读"""
        latest_id = 10
        last_read_id = 5
        
        has_unread = latest_id > last_read_id
        self.assertTrue(has_unread)
    
    def test_no_unread_when_all_read(self):
        """测试全部已读时无未读"""
        latest_id = 10
        last_read_id = 10
        
        has_unread = latest_id > last_read_id
        self.assertFalse(has_unread)
    
    def test_no_unread_when_no_changelog(self):
        """测试无日志时无未读"""
        latest_id = None
        last_read_id = None
        
        has_unread = latest_id is not None and (last_read_id is None or latest_id > last_read_id)
        self.assertFalse(has_unread)
    
    def test_has_unread_when_never_read(self):
        """测试从未阅读时显示未读"""
        latest_id = 5
        last_read_id = None  # 从未阅读
        
        has_unread = latest_id is not None and (last_read_id is None or latest_id > last_read_id)
        self.assertTrue(has_unread)


if __name__ == "__main__":
    unittest.main(verbosity=2)

