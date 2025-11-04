import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Header = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <header className="bg-white shadow">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo */}
          <Link to="/" className="flex items-center">
            <span className="text-2xl font-bold text-blue-600">EasyForm</span>
          </Link>

          {/* Navigation Links */}
          <div className="flex items-center gap-4">
            <Link
              to="/test-form"
              className="px-4 py-2 text-purple-600 hover:text-purple-800 font-medium"
            >
              Test Form
            </Link>
            {isAuthenticated ? (
              <>
                <span className="text-gray-700">
                  Welcome, <span className="font-semibold">{user?.username}</span>
                </span>
                <Link
                  to="/dashboard"
                  className="px-4 py-2 text-blue-600 hover:text-blue-800 font-medium"
                >
                  Dashboard
                </Link>
                <button
                  onClick={handleLogout}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-4 py-2 text-blue-600 hover:text-blue-800 font-medium"
                >
                  Login
                </Link>
                <Link
                  to="/register"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
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
