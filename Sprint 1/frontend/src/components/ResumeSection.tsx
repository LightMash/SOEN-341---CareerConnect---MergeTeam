import { useState, useEffect, type ChangeEvent } from "react";
import { uploadResume, listMyResumes, deleteResume, downloadResume, type Resume } from "../api";

export default function ResumeSection() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [error, setError] = useState<string>("");
  const [uploading, setUploading] = useState<boolean>(false);

  // Same pattern as App.tsx — token lives in local/session storage.
  const token = localStorage.getItem("token") || sessionStorage.getItem("token") || "";

  const loadResumes = () => {
    listMyResumes(token)
      .then(setResumes)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load resumes"));
  };

  // Load the list once, when this component first mounts.
  useEffect(() => {
    loadResumes();
  }, []);

  const handleFileSelected = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; // the "?" avoids crashing if the user cancels the file picker
    if (!file) return;

    setError("");
    setUploading(true);
    try {
      await uploadResume(file, token);
      loadResumes(); // refresh the list to show the new upload
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = ""; // reset the input so re-picking the same file still fires onChange
    }
  };

  const handleDelete = async (id: number) => {
    setError("");
    try {
      await deleteResume(id, token);
      loadResumes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const handleDownload = async (id: number, filename: string) => {
    setError("");
    try {
      await downloadResume(id, filename, token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    }
  };

  return (
    <div style={{ marginTop: 32, textAlign: "left" }}>
      <h3>My Resumes</h3>

      {error && <div style={{ color: "#dc2626", marginBottom: 8 }}>{error}</div>}

      {/* Both the MIME type and the file extension are listed — some OS file
          pickers key off one, some off the other, so both are needed to
          reliably show PDF and DOCX files while hiding everything else. */}
      <input
        type="file"
        accept="application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx"
        onChange={handleFileSelected}
        disabled={uploading}
      />
      {uploading && <p>Uploading...</p>}

      <ul style={{ marginTop: 16 }}>
        {resumes.map((r) => (
          <li key={r.id} style={{ marginBottom: 8 }}>
            {r.filename} — {new Date(r.uploaded_at).toLocaleDateString()}{" "}
            <button onClick={() => handleDownload(r.id, r.filename)}>Download</button>{" "}
            <button onClick={() => handleDelete(r.id)}>Delete</button>
          </li>
        ))}
      </ul>

      {resumes.length === 0 && <p style={{ color: "#64748b" }}>No resumes uploaded yet.</p>}
    </div>
  );
}