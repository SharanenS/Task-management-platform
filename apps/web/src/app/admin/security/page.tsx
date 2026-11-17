import { requireAdministrator } from "@/portals/admin/server";
export default async function Security() {
  await requireAdministrator();
  return (
    <>
      <p className="admin-eyebrow">YOUR ACCOUNT</p>
      <h1>Account security</h1>
      <p className="admin-intro">
        Keep your sign-in protected and your password private.
      </p>
      <section className="admin-panel" aria-labelledby="password-title">
        <span className="admin-card-symbol" aria-hidden="true">
          ◇
        </span>
        <h2 id="password-title">Password</h2>
        <p>
          Your password is managed by secure sign-in and is never displayed in
          Taskspace. You’ll verify your identity before choosing a new password.
        </p>
        <form method="post" action="/auth/change-password">
          <button className="admin-primary">
            Change password <span aria-hidden="true">↗</span>
          </button>
        </form>
      </section>
    </>
  );
}
