// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';
import Layout from './layout/Layout';
import Login from './pages/Login';
import Users from './pages/Users';
import SceneManager from './pages/SceneManager';
import SceneCreator from './pages/SceneCreator';
import Devices from './pages/Devices';
import Home from './pages/Home';
import ErrorBoundary from './components/ErrorBoundary';
import { AuthProvider } from './hooks/useAuth';
import 'antd/dist/reset.css';
import './index.css';
import Legal from './pages/Legal';

// ✅ Define all routes directly here (data router style)
const router = createBrowserRouter(
  [
    { path: '/login', element: <Login /> },
    {
      path: '/',
      element: <Layout />,
      errorElement: <ErrorBoundary />, // Built-in error handling
      children: [
        { index: true, element: <Home /> }, // Home dashboard
        { path: 'users', element: <Users /> },
        { path: 'legal', element: <Legal /> },
        { path: 'scenes', element: <SceneManager /> },
        { path: 'create-scene', element: <SceneCreator /> },
        { path: 'devices', element: <Devices /> },
      ],
    },
  ],
  {
    future: {
      v7_startTransition: true, // ✅ Opt-in early to React 18 concurrent transitions
    },
  }
);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </React.StrictMode>
);
