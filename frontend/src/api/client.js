import axios from 'axios';

// Create axios instance with base configuration
const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api', // Use Vite proxy in development
  withCredentials: true, // Send cookies with requests
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding tokens if needed
API.interceptors.request.use(
  (config) => {
    // You can add additional headers here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for handling errors
API.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle specific error codes
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // Unauthorized - redirect to login
          console.error('Unauthorized access - please login');
          break;
        case 403:
          console.error('Forbidden - insufficient permissions');
          break;
        case 404:
          console.error('Resource not found');
          break;
        case 500:
          console.error('Server error');
          break;
        default:
          console.error('An error occurred:', error.response.data);
      }
    }
    return Promise.reject(error);
  }
);

// Auth endpoints
export const authAPI = {
  login: (username, password) =>
    API.post('/auth/login', new URLSearchParams({ username, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  register: (userData) => API.post('/auth/signup', userData),
  logout: () => API.post('/auth/logout'),
  getCurrentUser: () => API.get('/users/me'),
};

// API Token endpoints
export const tokenAPI = {
  createToken: (name) => API.post('/api-tokens/', { name }),
  getTokens: () => API.get('/api-tokens/'),
  deleteToken: (tokenId) => API.delete(`/api-tokens/${tokenId}`),
};

// File endpoints
export const fileAPI = {
  uploadFile: (fileData) => API.post('/files/upload', fileData),
  getFiles: () => API.get('/files/'),
  downloadFile: (fileId) => API.get(`/files/${fileId}`),
  deleteFile: (fileId) => API.delete(`/files/${fileId}`),
};

// Form analysis endpoint
export const formAPI = {
  analyzeForm: (formData) => API.post('/form/analyze', formData),
};

export default API;
