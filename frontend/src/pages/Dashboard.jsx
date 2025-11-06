import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { tokenAPI, fileAPI, userAPI } from '../api/client';
import Header from '../components/Header';
import DeleteModal from '../components/DeleteModal';
import '../components/DeleteModal.css';

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
  const [personalInstructions, setPersonalInstructions] = useState('');
  const [instructionsSaving, setInstructionsSaving] = useState(false);
  const [instructionsDirty, setInstructionsDirty] = useState(false);
  
  // Modal state
  const [deleteModal, setDeleteModal] = useState({
    isOpen: false,
    type: null, // 'token' or 'file'
    item: null,
    isDeleting: false
  });

  useEffect(() => {
    loadData({ includeInstructions: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadData = async ({ includeInstructions = false } = {}) => {
    setLoading(true);
    try {
      const [tokensRes, filesRes] = await Promise.all([
        tokenAPI.getTokens(),
        fileAPI.getFiles(),
      ]);
      setTokens(tokensRes.data.tokens);
      setFiles(filesRes.data.files);
      setTotalStorage(filesRes.data.total_storage_bytes);

      if (includeInstructions) {
        try {
          const instructionsRes = await userAPI.getPersonalInstructions();
          const savedInstructions = instructionsRes.data.personal_instructions || '';
          setPersonalInstructions(savedInstructions);
          setInstructionsDirty(false);
        } catch (instructionsError) {
          console.error('Error loading personal instructions:', instructionsError);
          showMessage('Error loading personal instructions', 'error');
        }
      }
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
    setDeleteModal({
      isOpen: true,
      type: 'token',
      item: tokens.find(t => t.id === tokenId),
      isDeleting: false
    });
  };

  const handleDeleteFile = async (fileId) => {
    setDeleteModal({
      isOpen: true,
      type: 'file',
      item: files.find(f => f.id === fileId),
      isDeleting: false
    });
  };

  const confirmDelete = async () => {
    setDeleteModal(prev => ({ ...prev, isDeleting: true }));

    try {
      if (deleteModal.type === 'token') {
        await tokenAPI.deleteToken(deleteModal.item.id);
        showMessage('Token deleted successfully!');
      } else if (deleteModal.type === 'file') {
        await fileAPI.deleteFile(deleteModal.item.id);
        showMessage('File deleted successfully!');
      }
      
      await loadData();
      setDeleteModal({ isOpen: false, type: null, item: null, isDeleting: false });
    } catch (error) {
      console.error(`Error deleting ${deleteModal.type}:`, error);
      showMessage(`Error deleting ${deleteModal.type}`, 'error');
      setDeleteModal(prev => ({ ...prev, isDeleting: false }));
    }
  };

  const closeDeleteModal = () => {
    if (!deleteModal.isDeleting) {
      setDeleteModal({ isOpen: false, type: null, item: null, isDeleting: false });
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

  const handleSavePersonalInstructions = async () => {
    if (instructionsSaving || !instructionsDirty) {
      return;
    }

    setInstructionsSaving(true);
    try {
      const payload = {
        personal_instructions: personalInstructions && personalInstructions.trim().length > 0
          ? personalInstructions
          : null,
      };
      const response = await userAPI.updatePersonalInstructions(payload);
      const savedValue = response.data.personal_instructions || '';
      setPersonalInstructions(savedValue);
      setInstructionsDirty(false);
      showMessage('Personal instructions saved!');
    } catch (error) {
      console.error('Error saving personal instructions:', error);
      const detail = error.response?.data?.detail || 'Error saving personal instructions';
      showMessage(detail, 'error');
    } finally {
      setInstructionsSaving(false);
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

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-slate-950 transition-colors duration-300">
        <Header />
        <div className="flex items-center justify-center py-20">
          <div className="text-xl text-gray-600 dark:text-gray-300 transition-colors">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950 transition-colors duration-300">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white transition-colors">Welcome, {user?.username}!</h1>
              <p className="text-gray-600 dark:text-gray-300 mt-2 transition-colors">Manage your API tokens and uploaded files</p>
            </div>
            <Link
              to="/test-form"
              className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 dark:bg-purple-500 dark:hover:bg-purple-600 font-medium transition-colors"
            >
              Test Form
            </Link>
          </div>
        </div>

        {/* Message */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              message.type === 'error'
                ? 'bg-red-50 text-red-800 dark:bg-red-950/40 dark:text-red-200'
                : 'bg-green-50 text-green-800 dark:bg-emerald-950/40 dark:text-emerald-200'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* API Tokens Section */}
        <section className="mb-10">
          <div className="bg-white/95 dark:bg-slate-900/95 rounded-lg shadow dark:shadow-slate-900/50 border border-gray-100 dark:border-slate-800 p-6 transition-colors">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4 transition-colors">API Tokens</h2>
            <p className="text-gray-600 dark:text-gray-300 mb-6 transition-colors">
              Create tokens for your browser extension. Tokens are valid for at least 1 year.
            </p>

            {/* Create Token Form */}
            <form onSubmit={handleCreateToken} className="mb-6">
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="Token name (optional)"
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-indigo-400 transition-colors"
                  value={tokenName}
                  onChange={(e) => setTokenName(e.target.value)}
                />
                <button
                  type="submit"
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors"
                >
                  Create Token
                </button>
              </div>
            </form>

            {/* New Token Display (shown once after creation) */}
            {newToken && (
              <div className="mb-6 p-4 bg-yellow-50 dark:bg-amber-950/40 border-2 border-yellow-200 dark:border-amber-800 rounded-lg transition-colors">
                <p className="text-sm font-semibold text-yellow-900 dark:text-amber-100 mb-2 transition-colors">
                  ⚠️ Save this token now! It won't be shown again.
                </p>
                <div className="flex gap-2">
                  <code className="flex-1 p-3 bg-white dark:bg-slate-950 rounded border border-yellow-300 dark:border-amber-700 text-sm break-all text-gray-900 dark:text-gray-100 transition-colors">
                    {newToken.token}
                  </code>
                  <button
                    onClick={() => copyToClipboard(newToken.token)}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors whitespace-nowrap"
                  >
                    Copy
                  </button>
                </div>
                <button
                  onClick={() => setNewToken(null)}
                  className="mt-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Token List */}
            <div className="space-y-3">
              {tokens.length === 0 ? (
                <p className="text-gray-500 dark:text-gray-400 italic transition-colors">No tokens created yet.</p>
              ) : (
                tokens.map((token) => (
                  <div
                    key={token.id}
                    className="flex items-center justify-between p-4 border border-gray-200 dark:border-slate-700 rounded-lg bg-white/70 dark:bg-slate-900/70 transition-colors"
                  >
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100 transition-colors">{token.name || 'Unnamed Token'}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400 transition-colors">
                        Created: {new Date(token.created_at).toLocaleDateString()}
                      </p>
                      {token.last_used_at && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 transition-colors">
                          Last used: {new Date(token.last_used_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteToken(token.id)}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 dark:bg-red-500 dark:hover:bg-red-600 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Personal Instructions Section */}
        <section className="mb-10">
          <div className="bg-white/95 dark:bg-slate-900/95 rounded-lg shadow dark:shadow-slate-900/50 border border-gray-100 dark:border-slate-800 p-6 transition-colors">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-3 transition-colors">Personal Instructions</h2>
            <p className="text-gray-600 dark:text-gray-300 mb-4 transition-colors">
              Add optional notes that are stored locally and included when you upload new files.
            </p>
            <div>
              <label
                htmlFor="personalInstructions"
                className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2 transition-colors"
              >
                Personal Instructions
              </label>
              <textarea
                id="personalInstructions"
                value={personalInstructions}
                onChange={(e) => {
                  setPersonalInstructions(e.target.value);
                  setInstructionsDirty(true);
                }}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-indigo-400 transition-colors"
                placeholder="Add optional notes for yourself..."
              />
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mt-3">
                <div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 transition-colors">
                    These notes are stored with your account and sent to the AI when analyzing forms.
                  </p>
                  {instructionsDirty && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 font-medium mt-1 transition-colors">
                      Unsaved changes — click Save to keep them.
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handleSavePersonalInstructions}
                  disabled={instructionsSaving || !instructionsDirty}
                  className={`px-6 py-2 rounded-lg text-white transition ${
                    instructionsSaving || !instructionsDirty
                      ? 'bg-blue-300 dark:bg-blue-700/60 cursor-not-allowed'
                      : 'bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600'
                  }`}
                >
                  {instructionsSaving ? 'Saving...' : 'Save Instructions'}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Files Section */}
        <section className="mb-10">
          <div className="bg-white/95 dark:bg-slate-900/95 rounded-lg shadow dark:shadow-slate-900/50 border border-gray-100 dark:border-slate-800 p-6 transition-colors">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
              <div>
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-white transition-colors">Uploaded Files</h2>
                <p className="text-gray-600 dark:text-gray-300 mt-1 transition-colors">
                  Total storage: {formatFileSize(totalStorage)}
                </p>
              </div>
              <label className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors cursor-pointer text-center w-full sm:w-auto">
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

            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6 transition-colors">
              Supported formats: PNG, JPEG, GIF, WEBP, PDF (max 200MB per file)
            </p>

            {/* File List */}
            <div className="space-y-3">
              {files.length === 0 ? (
                <p className="text-gray-500 dark:text-gray-400 italic transition-colors">No files uploaded yet.</p>
              ) : (
                files.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-4 border border-gray-200 dark:border-slate-700 rounded-lg bg-white/70 dark:bg-slate-900/70 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div className="text-3xl">
                        {file.content_type.startsWith('image/') ? '🖼️' : '📄'}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100 transition-colors">{file.filename}</p>
                        <p className="text-sm text-gray-500 dark:text-gray-400 transition-colors">
                          {formatFileSize(file.file_size)} • Uploaded{' '}
                          {new Date(file.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteFile(file.id)}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 dark:bg-red-500 dark:hover:bg-red-600 transition-colors"
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

      {/* Delete Confirmation Modal */}
      <DeleteModal
        isOpen={deleteModal.isOpen}
        onClose={closeDeleteModal}
        onConfirm={confirmDelete}
        title={`Delete ${deleteModal.type === 'token' ? 'Token' : 'File'}?`}
        message={`Are you sure you want to delete this ${deleteModal.type}? This action cannot be undone.`}
        itemName={
          deleteModal.item
            ? deleteModal.type === 'token'
              ? deleteModal.item.name || 'Unnamed Token'
              : deleteModal.item.filename
            : ''
        }
        isDeleting={deleteModal.isDeleting}
      />
    </div>
  );
};

export default Dashboard;
