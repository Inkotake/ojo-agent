import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import apiClient from '../api/client';

interface NotificationState {
  // 未读更新日志数量
  unreadChangelogCount: number;
  // 最新已发布的更新日志ID
  latestChangelogId: number | null;
  // 本地缓存的已读ID（优雅降级）
  localReadId: number | null;
  // 是否正在加载
  loading: boolean;
  // 最后检查时间
  lastCheckedAt: number | null;

  // Actions
  fetchUnreadCount: () => Promise<void>;
  markAsRead: (changelogId: number) => Promise<void>;
  hasUnread: () => boolean;
  reset: () => void;
}

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set, get) => ({
      unreadChangelogCount: 0,
      latestChangelogId: null,
      localReadId: null,
      loading: false,
      lastCheckedAt: null,

      fetchUnreadCount: async () => {
        // 避免频繁请求（30秒内不重复请求）
        const { lastCheckedAt } = get();
        const now = Date.now();
        if (lastCheckedAt && now - lastCheckedAt < 30000) {
          return;
        }

        set({ loading: true });
        try {
          const res = await apiClient.get('/api/project/changelogs/unread-count');
          set({
            unreadChangelogCount: res.data.unread_count,
            latestChangelogId: res.data.latest_id,
            lastCheckedAt: now
          });
        } catch (e) {
          console.error('Failed to fetch unread count', e);
        } finally {
          set({ loading: false });
        }
      },

      markAsRead: async (changelogId: number) => {
        try {
          await apiClient.post('/api/project/changelogs/mark-read', { 
            changelog_id: changelogId 
          });
          set({
            unreadChangelogCount: 0,
            localReadId: changelogId
          });
        } catch (e) {
          // 后端失败时仍更新本地缓存（优雅降级）
          console.error('Failed to mark as read', e);
          set({ localReadId: changelogId });
        }
      },

      hasUnread: () => {
        const { unreadChangelogCount, latestChangelogId, localReadId } = get();
        
        // 优先使用后端计数
        if (unreadChangelogCount > 0) return true;
        
        // 本地缓存比较作为备用
        if (latestChangelogId && localReadId && latestChangelogId > localReadId) {
          return true;
        }
        
        return false;
      },

      reset: () => {
        set({
          unreadChangelogCount: 0,
          latestChangelogId: null,
          localReadId: null,
          loading: false,
          lastCheckedAt: null
        });
      }
    }),
    {
      name: 'notification-storage',
      // 只持久化部分状态
      partialize: (state) => ({
        localReadId: state.localReadId,
        latestChangelogId: state.latestChangelogId
      })
    }
  )
);

