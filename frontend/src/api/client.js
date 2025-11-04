import BaseApi from './baseApi';

const apiWithCookies = new BaseApi({ withCredentials: true }).instance;
const apiWithoutCookies = new BaseApi({ withCredentials: false }).instance;

// Auth endpoints
export const authAPI = {
  login: (username, password) =>
    apiWithCookies.post('/auth/login', new URLSearchParams({ username, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  register: (userData) => apiWithCookies.post('/auth/signup', userData),
  logout: () => apiWithCookies.post('/auth/logout'),
  getCurrentUser: () => apiWithCookies.get('/users/me'),
};

// API Token endpoints
export const tokenAPI = {
  createToken: (name) => apiWithCookies.post('/api-tokens/', { name }),
  getTokens: () => apiWithCookies.get('/api-tokens/'),
  deleteToken: (tokenId) => apiWithCookies.delete(`/api-tokens/${tokenId}`),
};

// File endpoints
export const fileAPI = {
  uploadFile: (fileData) => apiWithCookies.post('/files/upload', fileData),
  getFiles: () => apiWithCookies.get('/files/'),
  downloadFile: (fileId) => apiWithCookies.get(`/files/${fileId}`),
  deleteFile: (fileId) => apiWithCookies.delete(`/files/${fileId}`),
};

// Form analysis endpoint
export const formAPI = {
  analyzeForm: (formData) => apiWithCookies.post('/form/analyze', formData),
};

// User endpoints
export const userAPI = {
  getPersonalInstructions: () => apiWithCookies.get('/users/me/personal-instructions'),
  updatePersonalInstructions: (payload) => apiWithCookies.put('/users/me/personal-instructions', payload),
};

export { BaseApi, apiWithCookies, apiWithoutCookies };
export default apiWithCookies;
