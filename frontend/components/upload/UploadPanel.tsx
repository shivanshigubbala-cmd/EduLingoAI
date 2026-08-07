export default function UploadPanel() {
  return (
    <section className="w-full rounded-xl border border-gray-200 bg-white p-6 shadow-sm lg:w-80">
      <h2 className="text-lg font-semibold text-gray-900">Upload study material</h2>
      <p className="mt-1 text-sm text-gray-600">
        Add a PDF or image to prepare it for your diagnostic and study plan.
      </p>

      <button className="mt-5 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700">
        Choose a file
      </button>

      <p className="mt-4 text-sm text-gray-500">
        Upload is ready to be connected to the document endpoint.
      </p>
    </section>
  );
}
