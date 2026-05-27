import { useState, useEffect } from 'react';
import { Form, Input, Button, Card, message, Select, Space, Typography } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, SaveOutlined } from '@ant-design/icons';
import { getLLMConfig, updateLLMConfig, validateLLMConfig } from '../api';

const { Text } = Typography;

const PROVIDERS = [
  {
    value: 'dashscope-cn',
    label: '通义千问 DashScope（国内）',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
  },
  {
    value: 'dashscope-intl',
    label: '通义千问 DashScope（国际）',
    baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
  },
  {
    value: 'deepseek',
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
  },
  {
    value: 'openai',
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
  },
  {
    value: 'ollama',
    label: 'Ollama（Docker 访问本机）',
    baseUrl: 'http://host.docker.internal:11434/v1',
    model: 'qwen2.5:7b',
  },
  {
    value: 'custom',
    label: '自定义 OpenAI 兼容接口',
    baseUrl: '',
    model: '',
  },
] as const;

function providerFromBaseUrl(baseUrl: string): string {
  return PROVIDERS.find(provider => provider.baseUrl && provider.baseUrl === baseUrl)?.value || 'custom';
}

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
          provider: providerFromBaseUrl(config.base_url),
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

  const handleProviderChange = (value: string) => {
    const provider = PROVIDERS.find(item => item.value === value);
    if (!provider || provider.value === 'custom') return;
    form.setFieldsValue({
      base_url: provider.baseUrl,
      model: provider.model,
    });
    setValidationResult(null);
  };

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
            provider: 'dashscope-cn',
            base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            model: 'qwen-plus',
          }}
        >
          <Form.Item name="provider" label="供应商">
            <Select options={PROVIDERS.map(({ value, label }) => ({ value, label }))} onChange={handleProviderChange} />
          </Form.Item>

          <Form.Item
            name="api_key"
            label="API 密钥"
            extra={hasKey ? '已保存密钥；留空保存不会覆盖原密钥' : 'API 密钥仅保存在本地配置中'}
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
          <Text strong>选择供应商会自动填入接口地址和默认模型。</Text>
          <ul style={{ marginTop: 8 }}>
            <li>
              <Text code>DashScope 国内</Text> - <Text code>qwen-plus</Text>
            </li>
            <li>
              <Text code>DeepSeek</Text> - <Text code>deepseek-chat</Text>
            </li>
            <li>
              <Text code>Ollama</Text> - Docker 内访问本机用 <Text code>host.docker.internal</Text>
            </li>
          </ul>
        </Typography>
      </Card>
    </div>
  );
}

export default Settings;
