"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import "katex/dist/katex.min.css";
import "github-markdown-css/github-markdown-dark.css";

const mdComponents = {
  h1: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1
      className="text-2xl font-semibold text-white mt-6 mb-3 first:mt-0"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="text-xl font-semibold text-white mt-5 mb-2" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="text-lg font-medium text-white mt-4 mb-2" {...props}>
      {children}
    </h3>
  ),
  p: (props: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="text-editor-text/90 leading-relaxed mb-3" {...props} />
  ),
  ul: (props: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="list-disc pl-6 mb-3 space-y-1 text-editor-text/90" {...props} />
  ),
  ol: (props: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="list-decimal pl-6 mb-3 space-y-1 text-editor-text/90" {...props} />
  ),
  li: (props: React.HTMLAttributes<HTMLLIElement>) => (
    <li className="leading-relaxed" {...props} />
  ),
  a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a target="_blank" rel="noopener noreferrer" {...props} />
  ),
};

export default function MarkdownPreview({
  markdown,
  useMath = true,
}: Readonly<{
  markdown: string;
  useMath?: boolean;
}>) {
  const schema = {
    ...defaultSchema,
    attributes: {
      ...defaultSchema.attributes,
      div: [
        ...(defaultSchema.attributes?.div ?? []),
        ["align"],
      ],
      img: [
        ...(defaultSchema.attributes?.img ?? []),
        ["src"],
        ["alt"],
        ["title"],
        ["width"],
        ["height"],
      ],
      a: [
        ...(defaultSchema.attributes?.a ?? []),
        ["href"],
        ["title"],
      ],
    },
  };

  return (
    <div className="h-full overflow-y-auto bg-editor-bg py-6">
      <div className="w-full flex justify-center px-6">
        <div className="w-full max-w-3xl markdown-body !bg-transparent">
        <ReactMarkdown
          remarkPlugins={useMath ? [remarkGfm, remarkMath] : [remarkGfm]}
          rehypePlugins={
            useMath
              ? [rehypeRaw, [rehypeSanitize, schema], rehypeKatex]
              : [rehypeRaw, [rehypeSanitize, schema]]
          }
          components={mdComponents}
        >
          {markdown}
        </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

