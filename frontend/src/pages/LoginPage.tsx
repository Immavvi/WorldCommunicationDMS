import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { isLoading, login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setError(null);
    try {
      await login(String(values.get("email")), String(values.get("password")));
      const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";
      navigate(destination, { replace: true });
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Unable to sign in.");
    }
  }

  return (
    <section className="mx-auto max-w-md rounded-xl border border-slate-700 bg-slate-900 p-8 shadow-xl">
      <p className="text-sm font-medium tracking-[0.2em] text-cyan-400">WCDMS</p>
      <h1 className="mt-3 text-3xl font-semibold">Sign in</h1>
      <form className="mt-8 space-y-4" onSubmit={submit}>
        <label className="block">Email<input className="mt-1 w-full rounded bg-slate-800 p-2" name="email" type="email" required /></label>
        <label className="block">Password<input className="mt-1 w-full rounded bg-slate-800 p-2" name="password" type="password" required /></label>
        {error && <p className="text-sm text-rose-400" role="alert">{error}</p>}
        <button className="w-full rounded bg-cyan-500 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50" disabled={isLoading} type="submit">Sign in</button>
      </form>
    </section>
  );
}
