"use client";

import { useRef, useState, useCallback } from "react";

export interface UseFileDropOptions {
  accept: string[];
  maxBytes: number;
  onFiles: (files: File[]) => void;
  onReject?: (reason: string) => void;
}

export interface UseFileDropReturn {
  isDragging: boolean;
  dragHandlers: {
    onDragEnter: React.DragEventHandler;
    onDragOver: React.DragEventHandler;
    onDragLeave: React.DragEventHandler;
    onDrop: React.DragEventHandler;
  };
}

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
}

export function useFileDrop(options: UseFileDropOptions): UseFileDropReturn {
  const { accept, maxBytes, onFiles, onReject } = options;
  const [isDragging, setIsDragging] = useState(false);
  const dragDepthRef = useRef(0);

  const onDragEnter = useCallback<React.DragEventHandler>((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Only react when files are being dragged (not text/links)
    if (!e.dataTransfer.types.includes("Files")) return;
    dragDepthRef.current += 1;
    if (dragDepthRef.current === 1) {
      setIsDragging(true);
    }
  }, []);

  const onDragOver = useCallback<React.DragEventHandler>((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Ensure browser shows the "copy" drop cursor
    if (e.dataTransfer.types.includes("Files")) {
      e.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const onDragLeave = useCallback<React.DragEventHandler>((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Don't guard on types here — browsers may clear dataTransfer on dragleave,
    // which would prevent the depth counter from decrementing and leave isDragging stuck.
    dragDepthRef.current -= 1;
    if (dragDepthRef.current <= 0) {
      dragDepthRef.current = 0;
      setIsDragging(false);
    }
  }, []);

  const onDrop = useCallback<React.DragEventHandler>(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      dragDepthRef.current = 0;
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length === 0) return;

      const accepted: File[] = [];
      for (const file of files) {
        const ext = getExtension(file.name);
        if (!accept.includes(ext)) {
          onReject?.(`File "${file.name}" has an unsupported type. Allowed: ${accept.join(", ")}`);
          return;
        }
        if (file.size > maxBytes) {
          const mb = (maxBytes / 1024 / 1024).toFixed(0);
          onReject?.(`File "${file.name}" exceeds the ${mb} MB limit.`);
          return;
        }
        accepted.push(file);
      }

      if (accepted.length > 0) {
        onFiles(accepted);
      }
    },
    [accept, maxBytes, onFiles, onReject],
  );

  return {
    isDragging,
    dragHandlers: { onDragEnter, onDragOver, onDragLeave, onDrop },
  };
}
