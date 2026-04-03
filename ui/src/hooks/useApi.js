import { useState, useCallback } from 'react';
import { message } from 'antd';
import api from '../services/api';

export const useApi = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const callApi = useCallback(async (apiFunc) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFunc();
      setData(result);
      return result;
    } catch (err) {
      const errorMessage = err.message || 'Etwas ist schief gelaufen.';
      setError(errorMessage);
      message.error(`API Error: ${errorMessage}`);
      setData(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const get = useCallback(
    async (endpoint, options = {}) => {
      return callApi(() => api.get(endpoint, options));
    },
    [callApi]
  );

  const post = useCallback(
    async (endpoint, data, options = {}) => {
      return callApi(() => api.post(endpoint, data, options));
    },
    [callApi]
  );

  const patch = useCallback(
    async (endpoint, data) => {
      return callApi(() => api.patch(endpoint, data));
    },
    [callApi]
  );

  const delete_ = useCallback(
    async (endpoint) => {
      return callApi(() => api.delete(endpoint));
    },
    [callApi]
  );

  const resetData = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return {
    loading,
    error,
    data,
    callApi,
    get,
    post,
    patch,
    delete: delete_,
    resetData,
  };
};
