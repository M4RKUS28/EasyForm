import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';

const Home = () => {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-100 to-blue-200 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 transition-colors duration-300">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          {/* Hero Section */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-gray-900 dark:text-white mb-6 transition-colors">
            Welcome to <span className="text-blue-600 dark:text-blue-400 transition-colors">EasyForm</span>
          </h1>

          <p className="text-lg sm:text-xl text-gray-600 dark:text-gray-300 mb-8 max-w-2xl mx-auto transition-colors">
            AI-powered form filling made simple. Upload your documents, let our intelligent system analyze forms, and fill them automatically.
          </p>

          {/* Features */}
          <div className="grid md:grid-cols-3 gap-8 my-16 max-w-5xl mx-auto">
            <div className="bg-white/90 dark:bg-slate-900/90 p-6 rounded-lg shadow-md dark:shadow-none border border-gray-100 dark:border-slate-800 transition-colors">
              <div className="text-4xl mb-4">🤖</div>
              <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100 transition-colors">AI-Powered</h3>
              <p className="text-gray-600 dark:text-gray-300 transition-colors">
                Advanced AI analyzes forms and generates appropriate values based on your context
              </p>
            </div>

            <div className="bg-white/90 dark:bg-slate-900/90 p-6 rounded-lg shadow-md dark:shadow-none border border-gray-100 dark:border-slate-800 transition-colors">
              <div className="text-4xl mb-4">📄</div>
              <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100 transition-colors">Document Upload</h3>
              <p className="text-gray-600 dark:text-gray-300 transition-colors">
                Upload PDFs and images. Our system extracts information to fill forms accurately
              </p>
            </div>

            <div className="bg-white/90 dark:bg-slate-900/90 p-6 rounded-lg shadow-md dark:shadow-none border border-gray-100 dark:border-slate-800 transition-colors">
              <div className="text-4xl mb-4">🔒</div>
              <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-gray-100 transition-colors">Secure & Private</h3>
              <p className="text-gray-600 dark:text-gray-300 transition-colors">
                Your data is encrypted and stored securely. You have full control over your information
              </p>
            </div>
          </div>

          {/* CTA Buttons */}
          {isAuthenticated ? (
            <Link
              to="/dashboard"
              className="inline-block px-8 py-4 bg-blue-600 text-white text-lg font-semibold rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors shadow-lg"
            >
              Go to Dashboard
            </Link>
          ) : (
            <div className="flex gap-4 justify-center">
              <Link
                to="/register"
                className="px-8 py-4 bg-blue-600 text-white text-lg font-semibold rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors shadow-lg"
              >
                Get Started
              </Link>
              <Link
                to="/login"
                className="px-8 py-4 bg-white text-blue-600 text-lg font-semibold rounded-lg hover:bg-gray-50 transition-colors shadow-lg border-2 border-blue-600 dark:bg-transparent dark:text-blue-300 dark:border-blue-400 dark:hover:bg-blue-950/40"
              >
                Login
              </Link>
            </div>
          )}

          {/* How It Works */}
          <div className="mt-20">
            <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-10 transition-colors">How It Works</h2>
            <div className="grid md:grid-cols-4 gap-6 max-w-6xl mx-auto">
              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4 dark:bg-blue-500 transition-colors">
                  1
                </div>
                <h4 className="font-semibold mb-2 text-gray-900 dark:text-gray-100 transition-colors">Create Account</h4>
                <p className="text-gray-600 dark:text-gray-300 text-sm transition-colors">Sign up and get your API token</p>
              </div>

              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4 dark:bg-blue-500 transition-colors">
                  2
                </div>
                <h4 className="font-semibold mb-2 text-gray-900 dark:text-gray-100 transition-colors">Upload Documents</h4>
                <p className="text-gray-600 dark:text-gray-300 text-sm transition-colors">Add your PDFs and images</p>
              </div>

              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4 dark:bg-blue-500 transition-colors">
                  3
                </div>
                <h4 className="font-semibold mb-2 text-gray-900 dark:text-gray-100 transition-colors">Install Extension</h4>
                <p className="text-gray-600 dark:text-gray-300 text-sm transition-colors">Add our browser extension</p>
              </div>

              <div className="text-center">
                <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4 dark:bg-blue-500 transition-colors">
                  4
                </div>
                <h4 className="font-semibold mb-2 text-gray-900 dark:text-gray-100 transition-colors">Auto-Fill Forms</h4>
                <p className="text-gray-600 dark:text-gray-300 text-sm transition-colors">Let AI fill forms for you</p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Home;
