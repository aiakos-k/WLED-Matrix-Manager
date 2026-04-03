import { Modal, Form, Input, message } from 'antd';
import { useState } from 'react';
import api from '../services/api';

export default function ChangePasswordModal({ open, onClose }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (values) => {
    setLoading(true);

    try {
      await api.post('/auth/change-password', {
        old_password: values.old_password,
        new_password: values.new_password,
      });

      message.success('Password changed successfully');
      form.resetFields();
      onClose();
    } catch (err) {
      console.error('Password change error:', err);
      if (err.response?.data?.message) {
        message.error(err.response.data.message);
      } else {
        message.error('Failed to change password');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title="Change Password"
      open={open}
      onCancel={handleCancel}
      onOk={form.submit}
      confirmLoading={loading}
      okText="Change Password"
      cancelText="Cancel"
    >
      <Form form={form} layout="vertical" onFinish={handleChangePassword}>
        <Form.Item
          label="Current Password"
          name="old_password"
          rules={[{ required: true, message: 'Please enter your current password' }]}
        >
          <Input.Password placeholder="Enter your current password" />
        </Form.Item>

        <Form.Item
          label="New Password"
          name="new_password"
          rules={[
            { required: true, message: 'Please enter a new password' },
            { min: 6, message: 'Password must be at least 6 characters' },
          ]}
        >
          <Input.Password placeholder="Enter a new password" />
        </Form.Item>

        <Form.Item
          label="Confirm New Password"
          name="confirm_password"
          rules={[
            { required: true, message: 'Please confirm your new password' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue('new_password') === value) {
                  return Promise.resolve();
                }
                return Promise.reject(new Error('Passwords do not match'));
              },
            }),
          ]}
        >
          <Input.Password placeholder="Confirm your new password" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
