"use client";

import { useRef } from "react";
import VerifyButton from "./VerifyButton";

interface InputAreaProps {
  value: string;
  onChange: (value: string) => void;
  onVerify: () => void;
  loading: boolean;
  disabled?: boolean;
}

export default function InputArea({
  value,
  onChange,
  onVerify,
  loading,
  disabled,
}: InputAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isUrl =
    value.trim().startsWith("http://") || value.trim().startsWith("https://");

  return (
    <div
      className={`card-elevated transition-shadow ${
        disabled
          ? "opacity-60"
          : "focus-within:shadow-[0_2px_8px_rgba(125,41,242,0.12),0_0_0_2px_rgba(125,41,242,0.25)]"
      }`}
    >
      {isUrl && (
        <div className="rounded-t-lg bg-bria-purple/10 px-4 py-2">
          <span className="font-body text-sm text-bria-purple-2">
            We will fetch and check this page.
          </span>
        </div>
      )}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Paste a paragraph, article, or URL..."
        disabled={disabled}
        className="w-full min-h-[120px] resize-none border-none bg-transparent p-4 font-body text-[15px] text-text-primary placeholder:text-text-muted focus:outline-none"
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && value.trim()) {
            onVerify();
          }
        }}
      />
      <div className="flex items-center justify-between border-t border-border bg-muted/50 px-4 py-2 rounded-b-lg">
        <span className="font-body text-xs text-text-muted">
          {value.length.toLocaleString()} characters
        </span>
        <VerifyButton
          onClick={onVerify}
          loading={loading}
          disabled={!value.trim() || disabled}
        />
      </div>
    </div>
  );
}
