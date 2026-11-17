import Link from "next/link";
import { requireAdministrator } from "@/portals/admin/server";
export default async function AdminHome() {
  const { actor } = await requireAdministrator();
  return (
    <>
      <p className="admin-eyebrow">WORKSPACE ACCESS</p>
      <h1>Administration</h1>
      <p className="admin-intro">
        A clear place to manage your profile and keep your account secure.
      </p>
      <section className="admin-welcome" aria-labelledby="welcome-title">
        <div>
          <span className="admin-pill">Active administrator</span>
          <h2 id="welcome-title">Welcome, {actor.displayName}.</h2>
          <p>You’re signed in securely. Your account tools are ready below.</p>
        </div>
        <div className="admin-welcome-art" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
      </section>
      <section aria-labelledby="account-tools">
        <h2 id="account-tools" className="admin-section-title">
          Your account
        </h2>
        <div className="admin-cards">
          <Link href="/admin/profile" className="admin-action-card">
            <span className="admin-card-symbol" aria-hidden="true">
              ◎
            </span>
            <h3>Your profile</h3>
            <p>Review your name and account role.</p>
            <span className="admin-card-link">
              View profile <span aria-hidden="true">↗</span>
            </span>
          </Link>
          <Link href="/admin/security" className="admin-action-card">
            <span className="admin-card-symbol" aria-hidden="true">
              ◇
            </span>
            <h3>Account security</h3>
            <p>Change your password through secure sign-in.</p>
            <span className="admin-card-link">
              Manage security <span aria-hidden="true">↗</span>
            </span>
          </Link>
        </div>
      </section>
    </>
  );
}
