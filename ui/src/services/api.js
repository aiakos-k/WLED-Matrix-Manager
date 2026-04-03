// Build the base URL from environment variable
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

// Get user ID from localStorage (default to admin for testing)
const getUserId = () => {
  return localStorage.getItem('userId') || '1'; // Default to admin (ID 1)
};

// Get auth token from localStorage
const getAuthToken = () => {
  return localStorage.getItem('auth_token');
};

const getDefaultHeaders = () => {
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    'X-User-Id': getUserId(),
  };

  // Add auth token if available
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
};

const handleResponse = async (response) => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `HTTP error! status: ${response.status}`);
  }
  return response.json();
};

export const api = {
  async get(endpoint, options = {}) {
    const headers = { ...getDefaultHeaders(), ...options.headers };
    const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: 'GET',
      headers,
    });

    // Handle blob response type (for file downloads)
    if (options.responseType === 'blob') {
      return response.blob();
    }

    return handleResponse(response);
  },

  async post(endpoint, data, options = {}) {
    const headers = { ...getDefaultHeaders(), ...options.headers };
    const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;

    // Don't set Content-Type for multipart/form-data (let browser set it with boundary)
    if (data instanceof FormData) {
      delete headers['Content-Type'];
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: data instanceof FormData ? data : JSON.stringify(data),
    });
    return handleResponse(response);
  },

  async patch(endpoint, data) {
    const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: 'PATCH',
      headers: getDefaultHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse(response);
  },

  async delete(endpoint) {
    const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      method: 'DELETE',
      headers: getDefaultHeaders(),
    });
    if (!response.ok && response.status !== 204) {
      throw new Error('Delete failed');
    }
    return response.status === 204 ? true : await response.json();
  },
};

export default api;
