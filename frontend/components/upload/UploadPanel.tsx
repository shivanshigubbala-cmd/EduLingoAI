export default function UploadPanel() {
  return (
    <div className="w-full rounded-lg border bg-white p-6 shadow-sm lg:w-80">
      <h2 className="mb-4 text-xl font-semibold">Upload Panel</h2>

      <button className="w-full rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700">
        Upload File
      </button>

      <p className="mt-4 text-sm text-gray-500">
        No file uploaded.
      </p>
    </div>
  );
}