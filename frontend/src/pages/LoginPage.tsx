import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Terminal, LogIn, AlertCircle, UserPlus } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import Input from '../components/ui/Input';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Use relative path since frontend and API are on the same server
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || '登录失败');
      }

      login(data.token, data.user);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || '用户名或密码错误');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-xl p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-indigo-600 rounded-2xl mx-auto flex items-center justify-center mb-4 shadow-lg shadow-indigo-200">
            <Terminal className="text-white w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">OJ 批处理助手</h1>
          <p className="text-slate-500 mt-2">v9.0</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="用户名"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="admin 或 user"
            required
          />

          <Input
            label="密码"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-600">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Login Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-all active:scale-95"
          >
            {loading ? (
              <span>登录中...</span>
            ) : (
              <>
                <LogIn size={20} />
                <span>登录</span>
              </>
            )}
          </button>
        </form>

        {/* Register Link */}
        <div className="mt-6 text-center">
          <span className="text-sm text-slate-500">没有账号？</span>
          <Link 
            to="/register" 
            className="ml-2 text-sm text-indigo-600 hover:text-indigo-700 font-medium inline-flex items-center gap-1"
          >
            <UserPlus size={14} />
            立即注册
          </Link>
        </div>

        {/* Hint - 仅开发环境显示 */}
        {import.meta.env.DEV && (
          <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-100">
            <p className="text-xs text-blue-600">
              <strong>开发模式 - 测试账号:</strong><br />
              管理员: admin / admin123<br />
              普通用户: user / user123
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
