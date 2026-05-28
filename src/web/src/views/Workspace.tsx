import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Alert, Button, Checkbox, Empty, Input, List, Space, Tag, message } from 'antd';
import { FileTextOutlined, FolderOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  applyDevelopment,
  getWorkspaceFile,
  getWorkspaceInfo,
  getWorkspaceTree,
  proposeDevelopment,
  runDevelopmentTest,
} from '../api';
import type {
  DevelopmentProposal,
  TestCommandResult,
  WorkspaceFile,
  WorkspaceInfo,
  WorkspaceItem,
} from '../types';
import { getErrorMessage } from '../utils/error';

const { TextArea } = Input;

function Workspace() {
  const { projectId = '' } = useParams<{ projectId: string }>();
  const [info, setInfo] = useState<WorkspaceInfo | null>(null);
  const [items, setItems] = useState<WorkspaceItem[]>([]);
  const [selected, setSelected] = useState<WorkspaceFile | null>(null);
  const [checkedPaths, setCheckedPaths] = useState<string[]>([]);
  const [instruction, setInstruction] = useState('');
  const [proposal, setProposal] = useState<DevelopmentProposal | null>(null);
  const [testCommand, setTestCommand] = useState('npm test');
  const [testResult, setTestResult] = useState<TestCommandResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [developing, setDeveloping] = useState(false);
  const [applying, setApplying] = useState(false);
  const [testing, setTesting] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const workspaceInfo = await getWorkspaceInfo(projectId);
      setInfo(workspaceInfo);
      setSelected(null);
      setProposal(null);
      setCheckedPaths([]);
      if (workspaceInfo.configured) {
        setItems(await getWorkspaceTree(projectId));
      } else {
        setItems([]);
      }
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '项目工作区加载失败'));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const files = useMemo(() => items.filter((item) => item.type === 'file'), [items]);

  const openFile = async (item: WorkspaceItem) => {
    if (item.type !== 'file') {
      return;
    }
    try {
      setSelected(await getWorkspaceFile(item.path, projectId));
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '文件读取失败'));
    }
  };

  const togglePath = (path: string, checked: boolean) => {
    setCheckedPaths((current) => (checked ? [...new Set([...current, path])] : current.filter((item) => item !== path)));
  };

  const handlePropose = async () => {
    if (!instruction.trim()) {
      message.warning('请输入修改需求');
      return;
    }
    if (checkedPaths.length === 0) {
      message.warning('请至少选择一个文件');
      return;
    }
    setDeveloping(true);
    try {
      setProposal(await proposeDevelopment(instruction.trim(), checkedPaths, projectId));
      message.success('修改方案已生成');
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '修改方案生成失败'));
    } finally {
      setDeveloping(false);
    }
  };

  const handleApply = async () => {
    if (!proposal) {
      return;
    }
    setApplying(true);
    try {
      const result = await applyDevelopment(proposal.session_id);
      message.success(`已写回 ${result.written.length} 个文件`);
      setProposal(null);
      if (selected && result.written.includes(selected.path)) {
        setSelected(await getWorkspaceFile(selected.path, projectId));
      }
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '应用修改失败'));
    } finally {
      setApplying(false);
    }
  };

  const handleRunTest = async () => {
    if (!testCommand.trim()) {
      message.warning('请输入测试命令');
      return;
    }
    setTesting(true);
    try {
      const result = await runDevelopmentTest(testCommand.trim(), projectId);
      setTestResult(result);
      if (result.exit_code === 0) {
        message.success('测试命令执行成功');
      } else {
        message.warning(`测试命令退出码：${result.exit_code}`);
      }
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '测试命令执行失败'));
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="workspace-layout">
      <div className="page-surface workspace-panel">
        <div className="section-heading">
          <div>
            <h3>项目工作区</h3>
            <p>浏览当前项目绑定的代码目录，选择文件后生成修改方案或运行测试。</p>
          </div>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={loadWorkspace}>
            刷新
          </Button>
        </div>

        {info && !info.configured && (
          <Alert
            type="warning"
            showIcon
            message="当前项目还没有绑定目录"
            description="先在项目首页为该项目设置 root_path，然后再回到这里浏览、修改和测试代码。"
            style={{ marginBottom: 16 }}
          />
        )}

        {info?.configured && (
          <Space style={{ marginBottom: 12 }}>
            <Tag color="green">已绑定</Tag>
            <code>{info.root}</code>
          </Space>
        )}

        <div className="developer-console">
          <TextArea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            rows={4}
            placeholder="输入你希望修改的功能或问题，例如：给登录按钮增加 loading 状态，并补充错误提示。"
          />
          <Space style={{ marginTop: 10 }}>
            <Button type="primary" loading={developing} onClick={handlePropose}>
              生成修改方案
            </Button>
            <Tag>{checkedPaths.length} 个文件已选中</Tag>
          </Space>
        </div>

        <div className="developer-console">
          <Input
            value={testCommand}
            onChange={(event) => setTestCommand(event.target.value)}
            placeholder="输入测试命令，例如 npm test、pytest、python -m pytest"
          />
          <Space style={{ marginTop: 10 }}>
            <Button loading={testing} onClick={handleRunTest}>
              运行测试
            </Button>
            <Tag color={testResult?.exit_code === 0 ? 'green' : testResult ? 'red' : 'default'}>
              {testResult ? `退出码 ${testResult.exit_code}` : '未运行'}
            </Tag>
          </Space>
        </div>

        {files.length === 0 ? (
          <Empty description="暂无可浏览文件" />
        ) : (
          <List
            className="workspace-file-list"
            dataSource={items}
            loading={loading}
            renderItem={(item) => (
              <List.Item
                className={item.type === 'file' ? 'workspace-file-item' : 'workspace-directory-item'}
                onClick={() => openFile(item)}
              >
                <Space>
                  {item.type === 'file' && (
                    <Checkbox
                      checked={checkedPaths.includes(item.path)}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => togglePath(item.path, event.target.checked)}
                    />
                  )}
                  {item.type === 'directory' ? <FolderOutlined /> : <FileTextOutlined />}
                  <span>{item.path}</span>
                </Space>
              </List.Item>
            )}
          />
        )}
      </div>

      <div className="page-surface workspace-preview">
        {proposal ? (
          <>
            <div className="section-heading">
              <div>
                <h3>待应用修改</h3>
                <p>{proposal.summary}</p>
              </div>
              <Button type="primary" danger loading={applying} onClick={handleApply}>
                确认写回项目
              </Button>
            </div>
            {proposal.changes.map((change) => (
              <div className="diff-block" key={change.path}>
                <h4>{change.path}</h4>
                <pre>{change.diff || '文件内容将被更新'}</pre>
              </div>
            ))}
          </>
        ) : selected ? (
          <>
            <div className="section-heading">
              <div>
                <h3>{selected.path}</h3>
                <p>{selected.size} 字节</p>
              </div>
            </div>
            <pre>{selected.content}</pre>
          </>
        ) : (
          <Empty description="选择一个文件查看内容" />
        )}

        {testResult && (
          <div className="test-output">
            <h4>测试输出：{testResult.command}</h4>
            <pre>{testResult.output || '命令没有输出'}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default Workspace;
