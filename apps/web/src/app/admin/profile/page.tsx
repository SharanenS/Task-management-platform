import { requireAdministrator } from "@/portals/admin/server";
export default async function Profile() {
  const { actor } = await requireAdministrator();
  return (
    <>
      <p className="admin-eyebrow">YOUR ACCOUNT</p>
      <h1>Your profile</h1>
      <p className="admin-intro">Your identity in the Taskspace workspace.</p>
      <section className="admin-panel" aria-labelledby="profile-details">
        <h2 id="profile-details">Profile details</h2>
        <dl className="admin-details">
          <div>
            <dt>Name</dt>
            <dd>{actor.displayName}</dd>
          </div>
          <div>
            <dt>Company role</dt>
            <dd>Administrator</dd>
          </div>
          <div>
            <dt>Account status</dt>
            <dd>
              <span className="admin-pill admin-pill-light">Active</span>
            </dd>
          </div>
        </dl>
      </section>
    </>
  );
}
