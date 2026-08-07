import UploadPanel from "@/components/upload/UploadPanel";

export default function UploadPage() {
  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold text-gray-900">Upload material</h1>
      <p className="mt-2 text-sm text-gray-600">
        Upload notes or a syllabus to start building your learning plan.
      </p>
      <div className="mt-6">
        <UploadPanel />
      </div>
    </section>
  );
}
