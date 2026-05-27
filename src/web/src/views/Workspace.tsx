import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Checkbox, Empty, Input, List, message, Space, Tag } from 'antd';
import { FileTextOutlined, FolderOutlined, ReloadOutlined } from '@ant-design/icons';
import { applyDevelopment, getWorkspaceFile, getWorkspaceInfo, getWorkspaceTree, proposeDevelopment } from '../api';
import type { DevelopmentProposal, WorkspaceFile, WorkspaceInfo, WorkspaceItem } from '../types';

const { TextArea } = Input;

function Workspace() {
  const [info, setInfo] = useState<WorkspaceInfo | null>(null);
  const [items, setItems] = useState<WorkspaceItem[]>([]);
  const [selected, setSelected] = useState<WorkspaceFile | null>(null);
  const [checkedPaths, setCheckedPaths] = useState<string[]>([]);
  const [instruction, setInstruction] = useState('');
  const [proposal, setProposal] = useState<DevelopmentProposal | null>(null);
  const [loading, setLoading] = useState(false);
  const [developing, setDeveloping] = useState(false);
  const [applying, setApplying] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const workspaceInfo = await getWorkspaceInfo();
      setInfo(workspaceInfo);
      setSelected(null);
      setProposal(null);
      if (workspaceInfo.configured) {
        setItems(await getWorkspaceTree());
      } else {
        setItems([]);
      }
    } catch {
      message.error('项目工作区加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const files = useMemo(() => items.filter(item => item.type === 'file'), [items]);

  const openFile = async (item: WorkspaceItem) => {
    if (item.type !== 'file') return;
    try {
      setSelected(await getWorkspaceFile(item.path));
    } catch (err: unknown) {
      const error = err as Error;
      message.error(`文件读取失败：${error.message}`);
    }
  };

  const togglePath = (path: string, checked: boolean) => {
    setCheckedPaths((current) => (
      checked ? [...new Set([...current, path])] : current.filter(item => item !== path)
    ));
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
      setProposal(await proposeDevelopment(instruction.trim(), checkedPaths));
      message.success('修改方案已生成');
    } catch (err: unknown) {
      const error = err as Error;
      message.error(`修改方案生成失败：${error.message}`);
    } finally {
      setDeveloping(false);
    }
  };

  const handleApply = async () => {
    if (!proposal) return;
    setApplying(true);
    try {
      const result = await applyDevelopment(proposal.session_id);
      message.success(`已写回 ${result.written.length} 个文件`);
      setProposal(null);
      if (selected && result.written.includes(selected.path)) {
        setSelected(await getWorkspaceFile(selected.path));
      }
    } catch (err: unknown) {
      const error = err as Error;
      message.error(`应用修改失败：${error.message}`);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="workspace-layout">
      <div className="page-surface workspace-panel">
        <div className="section-heading">
          <div>
            <h3>项目工作区</h3>
            <p>只读浏览挂载到容器中的本地项目，代理会把文件树作为开发上下文。</p>
          </div>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={loadWorkspace}>
            刷新
          </Button>
        </div>

        {info && !info.configured && (
          <Alert
            type="warning"
            showIcon
            message="项目目录未配置"
            description="请通过 PROJECT_ROOT 环境变量把本地项目挂载到容器的 /workspace/project。"
            style={{ marginBottom: 16 }}
          />
        )}

        {info?.configured && (
          <Space style={{ marginBottom: 12 }}>
            <Tag color="green">已挂载</Tag>
            <code>{info.root}</code>
          </Space>
        )}

        <div className="developer-console">
          <TextArea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            rows={4}
            placeholder="输入你希望修改的功能或问题，例如：把登录按钮改成加载态，并补充错误提示"
          />
          <Space style={{ marginTop: 10 }}>
            <Button type="primary" loading={developing} onClick={handlePropose}>
              生成修改方案
            </Button>
            <Tag>{checkedPaths.length} 个文件已选择</Tag>
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
      </div>
    </div>
  );
}

export default Workspace;
