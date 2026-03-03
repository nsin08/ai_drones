import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { readMe } from '../lib/apiClient.js';
import { clearStoredSession, getAccessToken, mergeStoredSession } from '../auth/session.js';

function AuthGate({ title, body }) {
  return (
    <main className="v4-auth-gate">
      <section className="v4-auth-gate__card">
        <p className="v4-eyebrow">Authentication</p>
        <h1 className="v4-page__title">{title}</h1>
        <p className="v4-muted">{body}</p>
      </section>
    </main>
  );
}

export default function ProtectedRoute({ children }) {
  const location = useLocation();
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    let active = true;

    async function verify() {
      try {
        const identity = await readMe();
        if (!active) return;

        if (getAccessToken()) {
          mergeStoredSession({
            operatorId: identity.operator_id,
            username: identity.username,
            role: identity.role,
            allowedDrones: identity.allowed_drones || [],
          });
        }

        setStatus('ready');
      } catch (error) {
        if (!active) return;

        if (error?.response?.status === 401) {
          clearStoredSession();
          setStatus('unauthorized');
          return;
        }

        console.error('Session verification failed', error);
        setStatus('error');
      }
    }

    verify();
    return () => {
      active = false;
    };
  }, []);

  if (status === 'checking') {
    return <AuthGate title="Checking session" body="Validating your operator access before loading mission control." />;
  }

  if (status === 'unauthorized') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (status === 'error') {
    return <AuthGate title="Access check failed" body="Mission control could not verify your session. Retry after the API is available." />;
  }

  return children;
}
