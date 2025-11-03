import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { tokenAPI, fileAPI } from '../api/client';
import Header from '../components/Header';

const Dashboard = () => {
  const { user } = useAuth();
  const [tokens, setTokens] = useState([]);
  const [files, setFiles] = useState([]);
  const [totalStorage, setTotalStorage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tokenName, setTokenName] = useState('');
  const [newToken, setNewToken] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [tokensRes, filesRes] = await Promise.all([
        tokenAPI.getTokens(),
        fileAPI.getFiles(),
      ]);
      setTokens(tokensRes.data.tokens);
      setFiles(filesRes.data.files);
      setTotalStorage(filesRes.data.total_storage_bytes);
    } catch (error) {
      console.error('Error loading data:', error);
      showMessage('Error loading data', 'error');
    } finally {
      setLoading(false);
    }
  };

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  // Token Management
  const handleCreateToken = async (e) => {
    e.preventDefault();
    try {
      const response = await tokenAPI.createToken(tokenName || 'Browser Extension');
      setNewToken(response.data);
      setTokenName('');
      await loadData();
      showMessage('Token created successfully!');
    } catch (error) {
      console.error('Error creating token:', error);
      showMessage('Error creating token', 'error');
    }
  };

  const handleDeleteToken = async (tokenId) => {
    if (!confirm('Are you sure you want to delete this token?')) return;

    try {
      await tokenAPI.deleteToken(tokenId);
      await loadData();
      showMessage('Token deleted successfully!');
    } catch (error) {
      console.error('Error deleting token:', error);
      showMessage('Error deleting token', 'error');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    showMessage('Token copied to clipboard!');
  };

  // File Management
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      showMessage('Invalid file type. Only images and PDFs are allowed.', 'error');
      return;
    }

    // Validate file size (200MB)
    if (file.size > 200 * 1024 * 1024) {
      showMessage('File size exceeds 200MB limit.', 'error');
      return;
    }

    setUploadProgress(true);

    try {
      // Convert file to base64
      const base64 = await fileToBase64(file);

      await fileAPI.uploadFile({
        filename: file.name,
        content_type: file.type,
        data: base64,
      });

      await loadData();
      showMessage('File uploaded successfully!');
      e.target.value = ''; // Reset input
    } catch (error) {
      console.error('Error uploading file:', error);
      showMessage(error.response?.data?.detail || 'Error uploading file', 'error');
    } finally {
      setUploadProgress(false);
    }
  };

  const fileToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const base64 = reader.result.split(',')[1]; // Remove data:mime;base64, prefix
        resolve(base64);
      };
      reader.onerror = (error) => reject(error);
    });
  };

  const handleDeleteFile = async (fileId) => {
    if (!confirm('Are you sure you want to delete this file?')) return;

    try {
      await fileAPI.deleteFile(fileId);
      await loadData();
      showMessage('File deleted successfully!');
    } catch (error) {
      console.error('Error deleting file:', error);
      showMessage('Error deleting file', 'error');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="flex items-center justify-center py-20">
          <div className="text-xl text-gray-600">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Welcome, {user?.username}!</h1>
          <p className="text-gray-600 mt-2">Manage your API tokens and uploaded files</p>
        </div>

        {/* Message */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              message.type === 'error' ? 'bg-red-50 text-red-800' : 'bg-green-50 text-green-800'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* API Tokens Section */}
        <section className="mb-10">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">API Tokens</h2>
            <p className="text-gray-600 mb-6">
              Create tokens for your browser extension. Tokens are valid for at least 1 year.
            </p>

            {/* Create Token Form */}
            <form onSubmit={handleCreateToken} className="mb-6">
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="Token name (optional)"
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={tokenName}
                  onChange={(e) => setTokenName(e.target.value)}
                />
                <button
                  type="submit"
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                >
                  Create Token
                </button>
              </div>
            </form>

            {/* New Token Display (shown once after creation) */}
            {newToken && (
              <div className="mb-6 p-4 bg-yellow-50 border-2 border-yellow-200 rounded-lg">
                <p className="text-sm font-semibold text-yellow-900 mb-2">
                  ⚠️ Save this token now! It won't be shown again.
                </p>
                <div className="flex gap-2">
                  <code className="flex-1 p-3 bg-white rounded border border-yellow-300 text-sm break-all">
                    {newToken.token}
                  </code>
                  <button
                    onClick={() => copyToClipboard(newToken.token)}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition whitespace-nowrap"
                  >
                    Copy
                  </button>
                </div>
                <button
                  onClick={() => setNewToken(null)}
                  className="mt-2 text-sm text-gray-600 hover:text-gray-800"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Token List */}
            <div className="space-y-3">
              {tokens.length === 0 ? (
                <p className="text-gray-500 italic">No tokens created yet.</p>
              ) : (
                tokens.map((token) => (
                  <div
                    key={token.id}
                    className="flex items-center justify-between p-4 border border-gray-200 rounded-lg"
                  >
                    <div>
                      <p className="font-medium">{token.name || 'Unnamed Token'}</p>
                      <p className="text-sm text-gray-500">
                        Created: {new Date(token.created_at).toLocaleDateString()}
                      </p>
                      {token.last_used_at && (
                        <p className="text-sm text-gray-500">
                          Last used: {new Date(token.last_used_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteToken(token.id)}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition"
                    >
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Files Section */}
        <section>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-2xl font-semibold text-gray-900">Uploaded Files</h2>
                <p className="text-gray-600 mt-1">
                  Total storage: {formatFileSize(totalStorage)}
                </p>
              </div>
              <label className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition cursor-pointer">
                {uploadProgress ? 'Uploading...' : 'Upload File'}
                <input
                  type="file"
                  className="hidden"
                  accept="image/png,image/jpeg,image/jpg,image/gif,image/webp,application/pdf"
                  onChange={handleFileUpload}
                  disabled={uploadProgress}
                />
              </label>
            </div>

            <p className="text-sm text-gray-500 mb-6">
              Supported formats: PNG, JPEG, GIF, WEBP, PDF (max 200MB per file)
            </p>

            {/* File List */}
            <div className="space-y-3">
              {files.length === 0 ? (
                <p className="text-gray-500 italic">No files uploaded yet.</p>
              ) : (
                files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-4 border border-gray-200 rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <div className="text-3xl">
                        {file.content_type.startsWith('image/') ? '🖼️' : '📄'}
                      </div>
                      <div>
                        <p className="font-medium">{file.filename}</p>
                        <p className="text-sm text-gray-500">
                          {formatFileSize(file.file_size)} • Uploaded{' '}
                          {new Date(file.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteFile(file.id)}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition"
                    >
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Dashboard;
