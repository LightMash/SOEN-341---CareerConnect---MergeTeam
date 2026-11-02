import { useRef, useState } from "react";
import { getProfilePhoto, uploadProfilePhoto, deleteProfilePhoto } from "../api";
import { getInitials } from "../avatar";

// The "Profile photo" block: a big clickable avatar plus Upload / Change /
// Remove buttons. It is its own component because BOTH profile tabs use it —
// the job seeker's ProfileTab and the RecruiterProfileTab — so the upload
// logic exists exactly once.

interface ProfilePhotoProps {
  token: string;
  fullName: string; // for the initials shown when there is no photo
  // The current photo (blob URL) and a way to change it. The photo is owned
  // by Dashboard.tsx so the sidebar avatar updates the moment this block does.
  photoUrl: string | null;
  onPhotoChange: (url: string | null) => void;
}

// Client-side pre-checks: fast feedback only — the backend re-checks the real
// bytes and size (see upload_my_photo in routers/profile.py).
const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_PHOTO_MB = 2;

export default function ProfilePhoto({ token, fullName, photoUrl, onPhotoChange }: ProfilePhotoProps) {
  const photoInputRef = useRef<HTMLInputElement>(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [photoError, setPhotoError] = useState("");

  async function handlePhotoFile(file: File | undefined) {
    if (!file) return;

    if (!PHOTO_TYPES.includes(file.type)) {
      setPhotoError("Only JPG, PNG or WebP images can be used.");
      return;
    }
    if (file.size > MAX_PHOTO_MB * 1024 * 1024) {
      setPhotoError(`That image is over ${MAX_PHOTO_MB} MB. Try a smaller one.`);
      return;
    }

    setPhotoError("");
    setPhotoBusy(true);
    try {
      await uploadProfilePhoto(file, token);
      // Re-fetch what the server actually stored instead of previewing the
      // local file, so the screen always matches what was saved.
      onPhotoChange(await getProfilePhoto(token));
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : "Couldn't upload that photo.");
    } finally {
      setPhotoBusy(false);
    }
  }

  async function handlePhotoRemove() {
    setPhotoError("");
    setPhotoBusy(true);
    try {
      await deleteProfilePhoto(token);
      onPhotoChange(null); // back to initials
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : "Couldn't remove your photo.");
    } finally {
      setPhotoBusy(false);
    }
  }

  return (
    // The big circle is itself the "click to add your own picture" button;
    // the text buttons beside it do the same thing for people who don't
    // discover the circle.
    <section className="cc-section cc-photo-section" aria-label="Profile photo">
      <button
        type="button"
        className={`cc-avatar-lg ${photoUrl ? "has-photo" : ""}`}
        onClick={() => photoInputRef.current?.click()}
        disabled={photoBusy}
        aria-label={photoUrl ? "Change profile photo" : "Add a profile photo"}
        title={photoUrl ? "Change profile photo" : "Add a profile photo"}
      >
        {photoUrl ? <img src={photoUrl} alt="" /> : getInitials(fullName)}
        <span className="cc-avatar-hint" aria-hidden="true">
          {photoUrl ? "Change" : "Add photo"}
        </span>
      </button>

      <div className="cc-photo-info">
        <h2 className="cc-section-title">Profile photo</h2>
        <p className="cc-subtitle">JPG, PNG or WebP, up to {MAX_PHOTO_MB} MB</p>

        <div className="cc-form-actions">
          <button
            type="button"
            className="cc-upload-btn"
            onClick={() => photoInputRef.current?.click()}
            disabled={photoBusy}
          >
            {photoBusy ? "Working..." : photoUrl ? "Change photo" : "Upload photo"}
          </button>
          {photoUrl && (
            <button
              type="button"
              className="cc-upload-btn cc-btn-secondary"
              onClick={handlePhotoRemove}
              disabled={photoBusy}
            >
              Remove
            </button>
          )}
        </div>

        {photoError && (
          <p className="cc-error" role="alert">
            {photoError}
          </p>
        )}
      </div>

      <input
        ref={photoInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="cc-visually-hidden"
        tabIndex={-1}
        onChange={(e) => {
          handlePhotoFile(e.target.files?.[0]);
          e.target.value = ""; // so the same file can be picked again
        }}
      />
    </section>
  );
}
