import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/useTheme';

const MODE_CONFIG = {
  system: {
    label: 'Auto',
    description: 'Follow the system color scheme',
    next: 'light',
    icon: (
      <svg
        aria-hidden="true"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="4" width="18" height="14" rx="2" ry="2" />
        <line x1="8" y1="20" x2="16" y2="20" />
        <line x1="12" y1="16" x2="12" y2="20" />
      </svg>
    ),
  },
  light: {
    label: 'White',
    description: 'Always use the light theme',
    next: 'dark',
    icon: (
      <svg
        aria-hidden="true"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="5" />
        <line x1="12" y1="1" x2="12" y2="3" />
        <line x1="12" y1="21" x2="12" y2="23" />
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        <line x1="1" y1="12" x2="3" y2="12" />
        <line x1="21" y1="12" x2="23" y2="12" />
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
      </svg>
    ),
  },
  dark: {
    label: 'Dark',
    description: 'Always use the dark theme',
    next: 'system',
    icon: (
      <svg
        aria-hidden="true"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M21 12.79A9 9 0 0 1 11.21 3 7 7 0 1 0 21 12.79z" />
      </svg>
    ),
  },
};

const MODE_ACCENT_CLASS = {
  system:
    'border-gray-200 dark:border-slate-700 text-gray-700 dark:text-gray-200 hover:border-gray-300 dark:hover:border-slate-600 hover:text-gray-900 dark:hover:text-white',
  light:
    'border-amber-300 dark:border-amber-400 text-amber-700 dark:text-amber-200 hover:border-amber-400 dark:hover:border-amber-300 hover:text-amber-800 dark:hover:text-amber-100',
  dark:
    'border-indigo-400 dark:border-indigo-500 text-indigo-600 dark:text-indigo-200 hover:border-indigo-500 dark:hover:border-indigo-400 hover:text-indigo-300 dark:hover:text-indigo-100',
};

const Header = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const { mode, cycleMode } = useTheme();
  const currentMode = MODE_CONFIG[mode] ?? MODE_CONFIG.system;
  const nextModeKey = currentMode.next;
  const nextMode = MODE_CONFIG[nextModeKey] ?? MODE_CONFIG.system;
  const themeButtonTitle = `${currentMode.description}. Click to switch to ${nextMode.label}.`;
  const themeButtonClasses = `flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition-colors bg-white dark:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-500 dark:focus-visible:ring-indigo-400 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-900 ${MODE_ACCENT_CLASS[mode] ?? MODE_ACCENT_CLASS.system}`;

  const handleLogout = async () => {
    try {
      setIsLoggingOut(true);
      await logout();
      navigate('/');
    } catch (error) {
      console.error('Logout failed:', error);
      navigate('/');
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="bg-white/90 dark:bg-slate-900/90 backdrop-blur supports-[backdrop-filter]:backdrop-blur-md border-b border-gray-200 dark:border-slate-800 shadow transition-colors duration-300">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo */}
          <Link to="/" className="flex items-center">
            <span className="text-2xl font-bold text-blue-600 dark:text-blue-400 transition-colors">
              EasyForm
            </span>
          </Link>

          {/* Navigation Links */}
          <div className="flex items-center gap-3 sm:gap-4">
            <button
              type="button"
              onClick={cycleMode}
              className={themeButtonClasses}
              aria-label={`Theme: ${currentMode.label}. Next: ${nextMode.label}.`}
              title={themeButtonTitle}
            >
              {currentMode.icon}
              <span className="hidden sm:inline">
                {currentMode.label}
              </span>
            </button>
            {isAuthenticated ? (
              <>
                <span className="text-gray-700 dark:text-gray-200 transition-colors">
                  Welcome,{' '}
                  <span className="font-semibold text-gray-900 dark:text-white">
                    {user?.username}
                  </span>
                </span>
                <Link
                  to="/dashboard"
                  className="px-4 py-2 text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200 font-medium transition-colors"
                >
                  Dashboard
                </Link>
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                  className={`px-4 py-2 text-white rounded-lg transition-colors ${
                    isLoggingOut
                      ? 'bg-red-400 dark:bg-red-500 cursor-not-allowed'
                      : 'bg-red-600 hover:bg-red-700 dark:bg-red-500 dark:hover:bg-red-600'
                  }`}
                >
                  {isLoggingOut ? 'Logging out...' : 'Logout'}
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-4 py-2 text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200 font-medium transition-colors"
                >
                  Login
                </Link>
                <Link
                  to="/register"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors"
                >
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>
    </header>
  );
};

export default Header;
