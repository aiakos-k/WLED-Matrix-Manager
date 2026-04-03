import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Space,
  Button,
  Modal,
  Form,
  Input,
  Select,
  message,
  Tabs,
  Tag,
  Popconfirm,
} from 'antd';
import {
  EditOutlined,
  DeleteOutlined,
  UserAddOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import api from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';

export default function Users() {
  const { isAdmin, isLoading } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [pendingUsers, setPendingUsers] = useState([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  // Redirect non-admin users
  useEffect(() => {
    // Wait until auth is loaded before checking
    if (isLoading) return;

    if (!isAdmin) {
      message.error('Admin access required');
      navigate('/scenes');
    }
  }, [isAdmin, isLoading, navigate]);

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      // Fetch approved users
      const usersResponse = await api.get('/users');
      const usersArray = Array.isArray(usersResponse) ? usersResponse : usersResponse.data || [];
      setUsers(usersArray);

      // Fetch pending users
      const pendingResponse = await api.get('/auth/pending-users');
      setPendingUsers(pendingResponse.pending_users || []);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      message.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleAddEdit = async (values) => {
    try {
      setLoading(true);
      if (editingUser) {
        await api.patch(`/users/${editingUser.id}`, values);
        message.success('User updated successfully');
      } else {
        // Create user with password
        await api.post('/users', values);
        message.success('User created successfully');
      }
      setModalVisible(false);
      form.resetFields();
      fetchUsers();
    } catch (error) {
      console.error('Operation error:', error);
      message.error('Operation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (userId) => {
    try {
      setLoading(true);
      await api.delete(`/users/${userId}`);
      message.success('User deleted successfully');
      fetchUsers();
    } catch (error) {
      console.error('Delete error:', error);
      message.error('Delete failed');
    } finally {
      setLoading(false);
    }
  };

  const handleApprovePending = async (userId) => {
    try {
      setLoading(true);
      await api.post(`/auth/approve-user/${userId}`, {});
      message.success('User approved successfully');
      fetchUsers();
    } catch (error) {
      console.error('Approve error:', error);
      message.error('Failed to approve user');
    } finally {
      setLoading(false);
    }
  };

  const handleRejectPending = async (userId) => {
    try {
      setLoading(true);
      await api.delete(`/auth/reject-user/${userId}`);
      message.success('User request rejected');
      fetchUsers();
    } catch (error) {
      console.error('Reject error:', error);
      message.error('Failed to reject user');
    } finally {
      setLoading(false);
    }
  };

  const pendingColumns = [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Registered',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => new Date(date).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            size="small"
            icon={<CheckCircleOutlined />}
            onClick={() => handleApprovePending(record.id)}
          >
            Approve
          </Button>
          <Popconfirm
            title="Reject Registration"
            description="Are you sure you want to reject this registration?"
            onConfirm={() => handleRejectPending(record.id)}
            okText="Reject"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button danger size="small" icon={<CloseCircleOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const approvedColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role) => {
        // Handle both "admin" and "UserRole.ADMIN" formats
        const roleString = typeof role === 'string' ? role.split('.').pop().toLowerCase() : role;
        return roleString === 'admin' ? 'Admin' : 'User';
      },
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (is_active) => (
        <Tag color={is_active ? 'green' : 'red'}>{is_active ? 'Active' : 'Inactive'}</Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            onClick={() => {
              setEditingUser(record);
              form.setFieldsValue(record);
              setModalVisible(true);
            }}
          />
          <Popconfirm
            title="Delete user"
            description="Are you sure you want to delete this user?"
            onConfirm={() => handleDelete(record.id)}
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Button
          type="primary"
          icon={<UserAddOutlined />}
          onClick={() => {
            setEditingUser(null);
            form.resetFields();
            setModalVisible(true);
          }}
        >
          Add User
        </Button>

        <Tabs
          items={[
            {
              key: 'approved',
              label: `Approved Users (${users.length})`,
              children: (
                <Table dataSource={users} columns={approvedColumns} rowKey="id" loading={loading} />
              ),
            },
            {
              key: 'pending',
              label: `Pending Registrations (${pendingUsers.length})`,
              children: (
                <Table
                  dataSource={pendingUsers}
                  columns={pendingColumns}
                  rowKey="id"
                  loading={loading}
                  pagination={false}
                />
              ),
            },
          ]}
        />
      </Space>

      <Modal
        title={editingUser ? 'Edit User' : 'Add User'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={loading}
      >
        <Form form={form} onFinish={handleAddEdit} layout="vertical">
          <Form.Item
            name="username"
            label="Username"
            rules={[{ required: true, message: 'Please input username!' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Please input email!' },
              { type: 'email', message: 'Please input valid email!' },
            ]}
          >
            <Input />
          </Form.Item>
          {!editingUser && (
            <Form.Item
              name="password"
              label="Password"
              rules={[{ required: true, message: 'Please input password!' }]}
            >
              <Input.Password />
            </Form.Item>
          )}
          <Form.Item
            name="role"
            label="Role"
            rules={[{ required: true, message: 'Please select a role!' }]}
            initialValue="user"
          >
            <Select
              options={[
                { label: 'User (Limited Access)', value: 'user' },
                { label: 'Admin (Full Access)', value: 'admin' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
