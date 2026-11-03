import ProfilePhoto from "../ProfilePhoto";

interface RecruiterProfileTabProps {
  token: string;
  fullName: string;
  photoUrl: string | null;
  onPhotoChange: (url: string | null) => void;
}

// Recruiters have no professional profile or resumes (those are job-seeker
// features), but they still get an account photo. This tab is just the photo
// block for now; recruiter-specific profile fields (company, role, ...) can be
// added here later without touching the job seeker's ProfileTab.
export default function RecruiterProfileTab({
  token,
  fullName,
  photoUrl,
  onPhotoChange,
}: RecruiterProfileTabProps) {
  return (
    <>
      <header className="cc-main-head">
        <div>
          <h1 className="cc-title">Profile</h1>
          <p className="cc-subtitle">Your account</p>
        </div>
      </header>

      <ProfilePhoto token={token} fullName={fullName} photoUrl={photoUrl} onPhotoChange={onPhotoChange} />
    </>
  );
}
