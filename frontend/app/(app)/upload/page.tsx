import UploadPanel from "@/components/upload/UploadPanel";

export default function UploadPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Upload</h1>
      <p className="mt-1 text-sm text-gray-600">
        Upload your syllabus, notes, or textbook pages to get started.
      </p>
      <div className="mt-6">
        <UploadPanel />
      </div>
    </div>
  );
}