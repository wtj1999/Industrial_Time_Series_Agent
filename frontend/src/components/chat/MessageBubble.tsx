import { Bot, User } from 'lucide-react';
import type { Message } from '@/types';
import { Markdown } from './Markdown';
import { TypingDots } from '@/components/ui/Spinner';
import { cn } from '@/utils/cn';
import { formatTime } from '@/utils/format';

interface Props {
  message: Message;
  streaming?: boolean;
}

export function MessageBubble({ message, streaming }: Props) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const empty = !message.content;

  if (isSystem) {
    return (
      <div className="flex justify-center animate-fade-in">
        <div className="rounded-full border border-steel-200 bg-white/70 px-3 py-1 text-[11px] text-steel-500">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'group flex w-full gap-3 animate-slide-up',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <Avatar isUser={isUser} />
      <div
        className={cn(
          'flex flex-col max-w-[85%] md:max-w-[78%]',
          isUser ? 'items-end' : 'items-start',
        )}
      >
        <div
          className={cn(
            'rounded-2xl px-4 py-3 shadow-sm border',
            isUser
              ? 'bg-brand-600 text-white border-brand-600 rounded-tr-md'
              : 'bg-white text-steel-800 border-steel-200/80 rounded-tl-md',
          )}
        >
          {empty && streaming ? (
            <div className="py-1">
              <TypingDots />
            </div>
          ) : isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
          ) : (
            <Markdown content={message.content} />
          )}
        </div>
        {message.timestamp && (
          <span
            className={cn(
              'mt-1 text-[10px] text-steel-400 opacity-0 transition-opacity group-hover:opacity-100',
              isUser ? 'pr-1' : 'pl-1',
            )}
          >
            {formatTime(message.timestamp)}
          </span>
        )}
      </div>
    </div>
  );
}

function Avatar({ isUser }: { isUser: boolean }) {
  return (
    <div
      className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg shadow-sm',
        isUser
          ? 'bg-gradient-to-br from-brand-500 to-brand-700 text-white'
          : 'bg-gradient-to-br from-steel-700 to-steel-900 text-white',
      )}
    >
      {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
    </div>
  );
}
