import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Terminal, UserPlus, AlertCircle, LogIn, Ticket } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import Input from '../components/ui/Input';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    // 验证密码确认
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          username, 
          password,
          invite_code: inviteCode 
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || '注册失败');
      }

      // 注册成功后自动登录
      login(data.token, data.user);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || '注册失败');
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
          <h1 className="text-2xl font-bold text-slate-900">注册账号</h1>
          <p className="text-slate-500 mt-2">使用邀请码注册新账号</p>
        </div>

        {/* Register Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="用户名"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="3-20个字符"
            required
          />

          <Input
            label="密码"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="至少6个字符"
            required
          />

          <Input
            label="确认密码"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="再次输入密码"
            required
          />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              邀请码
            </label>
            <div className="relative">
              <Ticket className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                placeholder="请输入邀请码"
                required
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-600">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Register Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-all active:scale-95"
          >
            {loading ? (
              <span>注册中...</span>
            ) : (
              <>
                <UserPlus size={20} />
                <span>注册</span>
              </>
            )}
          </button>
        </form>

        {/* Login Link */}
        <div className="mt-6 text-center">
          <span className="text-sm text-slate-500">已有账号？</span>
          <Link 
            to="/login" 
            className="ml-2 text-sm text-indigo-600 hover:text-indigo-700 font-medium inline-flex items-center gap-1"
          >
            <LogIn size={14} />
            立即登录
          </Link>
        </div>
      </div>
    </div>
  );
}
