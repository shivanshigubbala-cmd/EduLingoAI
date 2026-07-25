"use client";

import { useRef, useState } from "react";

export default function UploadPanel() {
  const [files, setFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;
    setFiles((prev) => [...prev, ...Array.from(fileList)]);
    // TODO(P2-SHR2): POST to /documents/upload, get document_id back
  };

  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <p className="text-sm text-gray-600">
        Drag & drop your syllabus or notes here, or
      </p>
      <button
        onClick={() => inputRef.current?.click()}
        className="mt-3 rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800"
      >
        Browse files
      </button>
      <p className="mt-2 text-xs text-gray-400">PDF, PNG, or JPG</p>

      {files.length > 0 && (
        <ul className="mt-6 space-y-2 text-left text-sm text-gray-700">
          {files.map((f, i) => (
            <li key={i} className="rounded bg-gray-50 px-3 py-2">
              {f.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}