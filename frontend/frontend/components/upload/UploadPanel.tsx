"use client";

import { Upload } from "lucide-react";

export default function UploadPanel() {
  return (
    <aside className="w-80 bg-white rounded-xl shadow-md p-4 flex flex-col">
      <h2 className="text-xl font-semibold mb-4">Upload Files</h2>

      <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:border-blue-500 transition cursor-pointer">
        <Upload size={40} className="text-gray-500 mb-3" />

        <p className="font-medium">
          Drag & Drop Files Here
        </p>

        <p className="text-sm text-gray-500 mt-2">
          or click to browse
        </p>
      </div>

      <div className="mt-6">
        <h3 className="font-semibold mb-2">
          Uploaded Files
        </h3>

        <div className="text-gray-500 text-sm">
          No files uploaded yet.
        </div>
      </div>
    </aside>
  );
}