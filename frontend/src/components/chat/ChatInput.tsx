import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { ArrowUp, FileUp, Loader2, Paperclip, Square, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';

interface Props {
  streaming: boolean;
  injectedText?: string;
  onConsumeInjected?: () => void;
  onSubmit: (text: string, file: File | null) => void;
  onStop?: () => void;
}

const MAX_FILE_MB = 100;
const ALLOWED_EXTS = ['.csv', '.xlsx', '.parquet'];

export function ChatInput({
  streaming,
  injectedText,
  onConsumeInjected,
  onSubmit,
  onStop,
}: Props) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (injectedText) {
      setText(injectedText);
      onConsumeInjected?.();
      requestAnimationFrame(() => taRef.current?.focus());
    }
  }, [injectedText, onConsumeInjected]);

  // Auto-grow the textarea
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [text]);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setError(null);
    if (f) {
      const ext = '.' + (f.name.split('.').pop() ?? '').toLowerCase();
      if (!ALLOWED_EXTS.includes(ext)) {
        setError(`仅支持 ${ALLOWED_EXTS.join(' / ')} 格式`);
        return;
      }
      if (f.size > MAX_FILE_MB * 1024 * 1024) {
        setError(`文件大小不能超过 ${MAX_FILE_MB}MB`);
        return;
      }
    }
    setFile(f);
    e.target.value = '';
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (streaming) return;
    const trimmed = text.trim();
    if (!trimmed && !file) return;
    onSubmit(trimmed, file);
    setText('');
    setFile(null);
    setError(null);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  };

  return (
    <div className="border-t border-steel-200/70 bg-white/70 backdrop-blur-md px-4 sm:px-6 lg:px-10 py-4">
      <form onSubmit={handleSubmit} className="mx-auto w-full max-w-3xl">
        <div
          className={cn(
            'rounded-2xl border bg-white shadow-soft transition-shadow',
            'focus-within:border-brand-300 focus-within:shadow-glow',
            error ? 'border-rose-300' : 'border-steel-200',
          )}
        >
          {file && (
            <div className="flex items-center justify-between gap-2 px-3 pt-3">
              <div className="flex items-center gap-2 rounded-lg bg-steel-100 px-2.5 py-1.5 text-xs text-steel-700">
                <FileUp className="h-3.5 w-3.5 text-brand-600" />
                <span className="font-medium truncate max-w-[200px]">{file.name}</span>
                <span className="text-steel-400">
                  {(file.size / 1024).toFixed(1)} KB
                </span>
              </div>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="rounded p-1 text-steel-400 hover:bg-steel-100 hover:text-steel-700"
                aria-label="移除文件"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          <div className="flex items-end gap-2 px-3 py-2.5">
            <label
              className={cn(
                'inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-steel-500',
                'hover:bg-steel-100 hover:text-steel-700 transition-colors',
              )}
              title="上传 CSV / Excel / Parquet"
            >
              <Paperclip className="h-4 w-4" />
              <input
                type="file"
                accept={ALLOWED_EXTS.join(',')}
                onChange={handleFileChange}
                className="hidden"
                disabled={streaming}
              />
            </label>

            <textarea
              ref={taRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder={
                streaming ? '智能体正在思考…' : '描述你的分析需求，回车发送，Shift+Enter 换行'
              }
              disabled={streaming}
              className={cn(
                'flex-1 resize-none bg-transparent text-sm text-steel-900 placeholder:text-steel-400',
                'max-h-[200px] focus:outline-none disabled:opacity-60',
              )}
            />

            {streaming ? (
              <Button
                type="button"
                variant="danger"
                size="icon"
                onClick={onStop}
                title="停止生成"
                className="h-9 w-9"
              >
                <Square className="h-4 w-4" fill="currentColor" />
              </Button>
            ) : (
              <Button
                type="submit"
                size="icon"
                disabled={!text.trim() && !file}
                title="发送"
                className="h-9 w-9"
              >
                <ArrowUp className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        <div className="mt-2 flex h-5 items-center justify-between text-[11px]">
          <span className="text-rose-500">{error}</span>
          <span className="text-steel-400">
            {streaming ? (
              <span className="inline-flex items-center gap-1.5 text-brand-600">
                <Loader2 className="h-3 w-3 animate-spin" />
                流式输出中
              </span>
            ) : (
              <span className="hidden sm:inline">
                支持自然语言提问 · 数据文件可选 · 关键决策将弹出人工确认
              </span>
            )}
          </span>
        </div>
      </form>
    </div>
  );
}
