import PageSection from '../components/PageSection.jsx';

export default function LoginPage() {
  return (
    <main className="v4-login">
      <div className="v4-login__card">
        <PageSection title="Login Placeholder" eyebrow="Deferred Auth">
          <p className="v4-muted">
            Auth routing is reserved for a later hardening phase. The route exists now so the v4 route map does not
            need to change when login is introduced.
          </p>
        </PageSection>
      </div>
    </main>
  );
}
