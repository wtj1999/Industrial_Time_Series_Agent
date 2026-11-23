import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Copy, X } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/Button';
import { AccountAvatar } from './AccountAvatar';
import './Account.css';

export function AccountProfile({ onClose, onBindEmail }: {
  onClose: () => void;
  onBindEmail: () => void;
}) {
  const { user } = useAuth();
  const dialog = useRef<HTMLDialogElement>(null);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  if (!user) return null;

  function close() {
    dialog.current?.close();
    onClose();
  }

  async function copyAccountId(accountId: string) {
    try {
      await navigator.clipboard.writeText(accountId);
      setCopyStatus('copied');
    } catch {
      setCopyStatus('failed');
    }
  }

  return createPortal(
    <dialog
      ref={dialog}
      className="account-profile"
      aria-labelledby="account-profile-title"
      onCancel={event => { event.preventDefault(); close(); }}
      onClick={event => {
        if (event.target !== event.currentTarget) return;
        const box = event.currentTarget.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close();
      }}
    >
      <header className="account-profile-heading">
        <h2 id="account-profile-title">个人资料</h2>
        <Button type="button" autoFocus variant="ghost" size="icon" aria-label="关闭个人资料" onClick={close}>
          <X size={19} aria-hidden="true" />
        </Button>
      </header>
      <div className="account-profile-identity">
        <AccountAvatar username={user.username} />
        <div className="account-profile-name">
          <p>用户名</p>
          <strong>{user.username}</strong>
        </div>
      </div>
      <dl className="account-profile-details">
        <div className="account-profile-row">
          <dt>安全邮箱</dt>
          <dd>
            {user.email ? (
              <><span className="account-profile-value">{user.email}</span><span className="account-profile-verified"><Check size={13} aria-hidden="true" />已绑定</span></>
            ) : (
              <><span className="account-profile-value account-profile-unbound">未绑定</span><Button type="button" variant="subtle" size="sm" aria-haspopup="dialog" onClick={onBindEmail}>绑定邮箱</Button></>
            )}
          </dd>
        </div>
        <div className="account-profile-row">
          <dt>账户 ID</dt>
          <dd>
            <div className="account-profile-value">
              <code>{user.user_id}</code>
              <p className="account-profile-copy-status" role="status">
                {copyStatus === 'copied' ? '已复制' : copyStatus === 'failed' ? '复制失败，请选中账户 ID 手动复制' : ''}
              </p>
            </div>
            <Button type="button" variant="ghost" size="icon" title="复制账户 ID" aria-label="复制账户 ID" onClick={() => void copyAccountId(user.user_id)}>
              {copyStatus === 'copied' ? <Check size={17} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
            </Button>
          </dd>
        </div>
      </dl>
    </dialog>,
    document.body,
  );
}
