import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Empty, List, message, Space, Tag } from 'antd';
import { FileTextOutlined, FolderOutlined, ReloadOutlined } from '@ant-design/icons';
import { getWorkspaceFile, getWorkspaceInfo, getWorkspaceTree } from '../api';
import type { WorkspaceFile, WorkspaceInfo, WorkspaceItem } from '../types';

function Workspace() {
  const [info, setInfo] = useState<WorkspaceInfo | null>(null);
  const [items, setItems] = useState<WorkspaceItem[]>([]);
  const [selected, setSelected] = useState<WorkspaceFile | null>(null);
  const [loading, setLoading] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const workspaceInfo = await getWorkspaceInfo();
      setInfo(workspaceInfo);
      setSelected(null);
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
                  {item.type === 'directory' ? <FolderOutlined /> : <FileTextOutlined />}
                  <span>{item.path}</span>
                </Space>
              </List.Item>
            )}
          />
        )}
      </div>

      <div className="page-surface workspace-preview">
        {selected ? (
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
