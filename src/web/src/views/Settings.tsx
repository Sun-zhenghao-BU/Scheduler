import { useState, useEffect } from 'react';
import { Form, Input, Button, Card, message, Space, Typography } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, SaveOutlined } from '@ant-design/icons';
import { getLLMConfig, updateLLMConfig, validateLLMConfig } from '../api';

const { Text } = Typography;

function Settings() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; message: string } | null>(null);
  const [hasKey, setHasKey] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const config = await getLLMConfig();
        form.setFieldsValue({
          base_url: config.base_url,
          model: config.model,
        });
        setHasKey(config.has_api_key);
      } catch {
        message.error('配置加载失败');
      }
    };
    load();
  }, [form]);

  const handleSave = async (values: { api_key?: string; base_url: string; model: string }) => {
    setSaving(true);
    try {
      await updateLLMConfig(
        values.api_key || '',
        values.base_url,
        values.model,
      );
      message.success('配置已保存');
      setValidationResult(null);
      if (values.api_key) setHasKey(true);
    } catch {
      message.error('配置保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      const result = await validateLLMConfig();
      setValidationResult(result);
      if (result.valid) {
        message.success('连接测试成功');
      } else {
        message.error(result.message);
      }
    } catch {
      message.error('连接测试失败');
    } finally {
      setValidating(false);
    }
  };

  return (
    <div style={{ maxWidth: 600 }}>
      <h2 style={{ marginBottom: 24 }}>模型设置</h2>

      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          initialValues={{
            base_url: 'https://api.openai.com/v1',
            model: 'gpt-4',
          }}
        >
          <Form.Item
            name="api_key"
            label="API 密钥"
            extra="API 密钥仅保存在本地配置中"
          >
            <Input.Password
              placeholder="sk-..."
              autoComplete="off"
            />
          </Form.Item>

          <Form.Item
            name="base_url"
            label="接口地址"
            extra="兼容 OpenAI 格式的接口地址"
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Form.Item name="model" label="模型">
            <Input placeholder="gpt-4" />
          </Form.Item>

          <Space>
            <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
              保存
            </Button>
            <Button onClick={handleValidate} loading={validating} disabled={!hasKey}>
              测试连接
            </Button>
          </Space>
        </Form>
      </Card>

      {validationResult && (
        <Card style={{ marginTop: 16 }}>
          <Space>
            {validationResult.valid ? (
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
            ) : (
              <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 20 }} />
            )}
            <Text>{validationResult.message}</Text>
          </Space>
        </Card>
      )}

      <Card style={{ marginTop: 16 }} title="常用配置" size="small">
        <Typography>
          <Text strong>常用接口地址：</Text>
          <ul style={{ marginTop: 8 }}>
            <li>
              <Text code>OpenAI</Text> - 接口地址：<Text code>https://api.openai.com/v1</Text>
            </li>
            <li>
              <Text code>DeepSeek</Text> - 接口地址：<Text code>https://api.deepseek.com/v1</Text>
            </li>
            <li>
              <Text code>通义千问</Text> - 接口地址：<Text code>https://dashscope.aliyuncs.com/compatible-mode/v1</Text>
            </li>
            <li>
              <Text code>Ollama（本地）</Text> - 接口地址：<Text code>http://localhost:11434/v1</Text>
            </li>
          </ul>
        </Typography>
      </Card>
    </div>
  );
}

export default Settings;
