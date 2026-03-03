import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { clearStoredSession, readStoredSession, writeStoredSession } from '../auth/session.js';
import PageSection from '../components/PageSection.jsx';
import { login, readMe } from '../lib/apiClient.js';

export default function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: 'admin',
    password: 'admin123',
    remember: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const returnTo = location.state?.from?.pathname || '/dashboard';

  useEffect(() => {
    let active = true;

    async function resumeSession() {
      if (!readStoredSession()) return;
      try {
        await readMe();
        if (active) navigate(returnTo, { replace: true });
      } catch (resumeError) {
        if (resumeError?.response?.status === 401) {
          clearStoredSession();
        }
      }
    }

    resumeSession();
    return () => {
      active = false;
    };
  }, [navigate, returnTo]);

  function updateField(field) {
    return (event) => {
      const value = field === 'remember' ? event.target.checked : event.target.value;
      setForm((prev) => ({ ...prev, [field]: value }));
    };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      const token = await login({
        username: form.username.trim(),
        password: form.password,
      });

      writeStoredSession({
        accessToken: token.access_token,
        operatorId: token.operator_id,
        username: token.username,
        role: token.role,
      }, form.remember ? 'local' : 'session');

      const identity = await readMe();
      writeStoredSession({
        accessToken: token.access_token,
        operatorId: identity.operator_id,
        username: identity.username,
        role: identity.role,
        allowedDrones: identity.allowed_drones || [],
      }, form.remember ? 'local' : 'session');

      navigate(returnTo, { replace: true });
    } catch (loginError) {
      clearStoredSession();
      setError(loginError?.response?.data?.detail || 'Unable to sign in with those credentials.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="v4-login">
      <div className="v4-login__card">
        <PageSection title="Operator Sign-In" eyebrow="Mission Control">
          <p className="v4-muted">
            Authenticate before accessing the live dashboard, mission planner, and fleet controls.
          </p>

          <form className="v4-login__form" onSubmit={handleSubmit}>
            <label className="v4-login__field">
              <span>Username</span>
              <input
                type="text"
                value={form.username}
                onChange={updateField('username')}
                autoComplete="username"
                disabled={submitting}
              />
            </label>

            <label className="v4-login__field">
              <span>Password</span>
              <input
                type="password"
                value={form.password}
                onChange={updateField('password')}
                autoComplete="current-password"
                disabled={submitting}
              />
            </label>

            <label className="v4-login__check">
              <input
                type="checkbox"
                checked={form.remember}
                onChange={updateField('remember')}
                disabled={submitting}
              />
              <span>Keep me signed in on this browser</span>
            </label>

            {error && (
              <p className="v4-login__error" role="alert">
                {error}
              </p>
            )}

            <div className="v4-login__actions">
              <button type="submit" className="v4-login__submit" disabled={submitting}>
                {submitting ? 'Signing In...' : 'Sign In'}
              </button>
            </div>
          </form>

          <p className="v4-login__hint">
            Demo accounts: <code>admin / admin123</code>, <code>pilot1 / pilot123</code>, <code>observer / observe123</code>.
          </p>
        </PageSection>
      </div>
    </main>
  );
}
