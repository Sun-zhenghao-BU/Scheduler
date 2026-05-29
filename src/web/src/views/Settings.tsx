import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Select, Space, Typography, message } from 'antd';
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
    label: 'Ollama（Docker 访问宿主机）',
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
  return PROVIDERS.find((provider) => provider.baseUrl && provider.baseUrl === baseUrl)?.value || 'custom';
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
          product_manager_model: config.product_manager_model || config.model,
          developer_model: config.developer_model || config.model,
          tester_model: config.tester_model || config.model,
          codegen_model: config.codegen_model || config.model,
          product_manager_timeout: config.product_manager_timeout,
          developer_timeout: config.developer_timeout,
          tester_timeout: config.tester_timeout,
          codegen_timeout: config.codegen_timeout,
        });
        setHasKey(config.has_api_key);
      } catch {
        message.error('配置加载失败');
      }
    };
    load();
  }, [form]);

  const handleProviderChange = (value: string) => {
    const provider = PROVIDERS.find((item) => item.value === value);
    if (!provider || provider.value === 'custom') return;
    form.setFieldsValue({
      base_url: provider.baseUrl,
      model: provider.model,
      product_manager_model: provider.model,
      developer_model: provider.model,
      tester_model: provider.model,
      codegen_model: provider.model,
    });
    setValidationResult(null);
  };

  const handleSave = async (values: Record<string, string | number | undefined>) => {
    setSaving(true);
    try {
      await updateLLMConfig({
        api_key: String(values.api_key || ''),
        base_url: String(values.base_url || ''),
        model: String(values.model || ''),
        product_manager_model: String(values.product_manager_model || ''),
        developer_model: String(values.developer_model || ''),
        tester_model: String(values.tester_model || ''),
        codegen_model: String(values.codegen_model || ''),
        product_manager_timeout: Number(values.product_manager_timeout || 120),
        developer_timeout: Number(values.developer_timeout || 300),
        tester_timeout: Number(values.tester_timeout || 180),
        codegen_timeout: Number(values.codegen_timeout || 300),
      });
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
    <div style={{ maxWidth: 760 }}>
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
            product_manager_model: 'qwen-plus',
            developer_model: 'qwen-plus',
            tester_model: 'qwen-plus',
            codegen_model: 'qwen-plus',
            product_manager_timeout: 120,
            developer_timeout: 300,
            tester_timeout: 180,
            codegen_timeout: 300,
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
            <Input.Password placeholder="sk-..." autoComplete="off" />
          </Form.Item>

          <Form.Item name="base_url" label="接口地址" extra="兼容 OpenAI 格式的接口地址">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Form.Item name="model" label="默认模型">
            <Input placeholder="gpt-4o-mini" />
          </Form.Item>

          <Card size="small" title="角色模型" style={{ marginBottom: 16 }}>
            <Form.Item name="product_manager_model" label="产品经理模型">
              <Input placeholder="留空则使用默认模型" />
            </Form.Item>
            <Form.Item name="developer_model" label="实施方案模型">
              <Input placeholder="建议使用更强的模型" />
            </Form.Item>
            <Form.Item name="tester_model" label="测试评审模型">
              <Input placeholder="建议使用结构化输出稳定的模型" />
            </Form.Item>
            <Form.Item name="codegen_model" label="代码修改模型">
              <Input placeholder="建议与实施方案模型分开" />
            </Form.Item>
          </Card>

          <Card size="small" title="阶段超时（秒）" style={{ marginBottom: 16 }}>
            <Space wrap>
              <Form.Item name="product_manager_timeout" label="产品经理" style={{ marginBottom: 0 }}>
                <InputNumber min={30} max={900} />
              </Form.Item>
              <Form.Item name="developer_timeout" label="实施方案" style={{ marginBottom: 0 }}>
                <InputNumber min={30} max={900} />
              </Form.Item>
              <Form.Item name="tester_timeout" label="测试评审" style={{ marginBottom: 0 }}>
                <InputNumber min={30} max={900} />
              </Form.Item>
              <Form.Item name="codegen_timeout" label="代码修改" style={{ marginBottom: 0 }}>
                <InputNumber min={30} max={900} />
              </Form.Item>
            </Space>
          </Card>

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

      <Card style={{ marginTop: 16 }} title="使用建议" size="small">
        <ul style={{ marginBottom: 0 }}>
          <li>产品经理阶段可以使用响应更快的通用模型。</li>
          <li>实施方案和代码修改阶段建议使用更强的代码模型，并设置更长超时。</li>
          <li>测试评审阶段更看重结构化 JSON 输出稳定性。</li>
          <li>如果某一阶段频繁超时，优先提升该阶段超时或更换该角色模型，而不是统一抬高所有超时。</li>
        </ul>
      </Card>
    </div>
  );
}

export default Settings;
