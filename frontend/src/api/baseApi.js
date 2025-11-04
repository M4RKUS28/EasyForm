import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api';

class BaseApi {
  constructor({ baseURL = API_URL, withCredentials = true } = {}) {
    this.api = axios.create({
      baseURL,
      withCredentials,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.withCredentials = withCredentials;
    this.isRefreshing = false;
    this.failedQueue = [];

    this.api.interceptors.request.use(
      (config) => config,
      (error) => Promise.reject(error)
    );

    this.api.interceptors.response.use(
      (response) => response,
      (error) => this.handleResponseError(error)
    );
  }

  processQueue(error) {
    this.failedQueue.forEach((p) => (error ? p.reject(error) : p.resolve()));
    this.failedQueue = [];
  }

  async handleResponseError(error) {
    if (error.response?.status === 429) {
      return Promise.reject(error);
    }

    if (!this.withCredentials) {
      this.logCommonErrors(error);
      return Promise.reject(error);
    }

    const originalRequest = error.config;
    const originalResponseType = originalRequest?.responseType;

    const isAuthEndpoint = originalRequest.url?.includes('/auth/login') ||
      originalRequest.url?.includes('/auth/signup') ||
      originalRequest.url?.includes('/auth/refresh');

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      if (this.isRefreshing) {
        return new Promise((resolve, reject) => {
          this.failedQueue.push({ resolve, reject });
        }).then(() => {
          if (originalResponseType) {
            originalRequest.responseType = originalResponseType;
          }
          return this.api(originalRequest);
        });
      }

      originalRequest._retry = true;
      this.isRefreshing = true;

      try {
        await axios.post('/api/auth/refresh', null, { withCredentials: true });
        this.processQueue(null);
        if (originalResponseType) {
          originalRequest.responseType = originalResponseType;
        }
        return this.api(originalRequest);
      } catch (refreshError) {
        this.processQueue(refreshError);
        if (typeof window !== 'undefined' && window.location.pathname !== '/auth/login') {
          window.location.href = '/auth/login';
        }
        return Promise.reject(refreshError);
      } finally {
        this.isRefreshing = false;
      }
    }

    this.logCommonErrors(error);
    return Promise.reject(error);
  }

  logCommonErrors(error) {
    if (!error.response) {
      return;
    }

    switch (error.response.status) {
      case 401:
        console.error('Unauthorized - please login');
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

  get instance() {
    return this.api;
  }
}

export default BaseApi;
