import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

/**
 * Markdown renderer used inside assistant bubbles.
 * - GitHub-flavored markdown (tables, task lists, strikethrough)
 * - Syntax-highlighted code blocks via highlight.js
 */
export const Markdown = memo(function Markdown({ content }: { content: string }) {
  if (!content) return null;
  return (
    <div className="md-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          a: ({ node: _node, ...props }) => (
            <a target="_blank" rel="noreferrer noopener" {...props} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
