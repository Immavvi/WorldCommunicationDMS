import { FormEvent, useCallback, useEffect, useState } from "react";

import { assignUserRole, createUser, listUsers, resetUserPassword, setUserActive } from "../api/users";
import { ApiError, type User } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const roles = ["SUPER-ADMIN", "ADMIN"] as const;

export function UsersPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);

  const loadUsers = useCallback(async () => {
    if (!token) return;
    try {
      setUsers((await listUsers(token)).items);
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Unable to load users.");
    }
  }, [token]);

  useEffect(() => { void loadUsers(); }, [loadUsers]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const data = new FormData(event.currentTarget);
    try {
      await createUser(token, {
        email: String(data.get("email")),
        password: String(data.get("password")),
        role_name: String(data.get("role_name")) as (typeof roles)[number],
      });
      event.currentTarget.reset();
      await loadUsers();
    } catch (exception) { setError(exception instanceof ApiError ? exception.message : "Unable to create user."); }
  }

  async function updateRole(userId: string, roleName: (typeof roles)[number]) {
    if (!token) return;
    await assignUserRole(token, userId, roleName);
    await loadUsers();
  }

  async function updateActive(user: User) {
    if (!token) return;
    await setUserActive(token, user.id, !user.is_active);
    await loadUsers();
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !selectedUser) return;
    const password = String(new FormData(event.currentTarget).get("new_password"));
    try {
      await resetUserPassword(token, selectedUser, password);
      event.currentTarget.reset();
      setSelectedUser(null);
    } catch (exception) { setError(exception instanceof ApiError ? exception.message : "Unable to reset password."); }
  }

  return <section className="space-y-8"><div><p className="text-sm font-medium tracking-[0.2em] text-cyan-400">SUPER-ADMIN</p><h1 className="mt-2 text-3xl font-semibold">Users</h1></div>{error && <p className="text-rose-400" role="alert">{error}</p>}<form className="grid gap-3 rounded-xl border border-slate-700 bg-slate-900 p-5 md:grid-cols-4" onSubmit={create}><input className="rounded bg-slate-800 p-2" name="email" placeholder="Email" type="email" required /><input className="rounded bg-slate-800 p-2" minLength={12} name="password" placeholder="Temporary password" type="password" required /><select className="rounded bg-slate-800 p-2" name="role_name" defaultValue="ADMIN">{roles.map((role) => <option key={role}>{role}</option>)}</select><button className="rounded bg-cyan-500 px-4 py-2 font-semibold text-slate-950" type="submit">Create user</button></form>{selectedUser && <form className="flex gap-3 rounded-xl border border-amber-600 bg-slate-900 p-5" onSubmit={resetPassword}><input className="flex-1 rounded bg-slate-800 p-2" minLength={12} name="new_password" placeholder="New password" type="password" required /><button className="rounded bg-amber-400 px-4 py-2 font-semibold text-slate-950" type="submit">Set password</button><button type="button" onClick={() => setSelectedUser(null)}>Cancel</button></form>}<div className="overflow-x-auto rounded-xl border border-slate-700"><table className="w-full text-left text-sm"><thead className="bg-slate-900 text-slate-300"><tr><th className="p-3">Email</th><th className="p-3">Role</th><th className="p-3">Status</th><th className="p-3">Actions</th></tr></thead><tbody>{users.map((user) => <tr className="border-t border-slate-800" key={user.id}><td className="p-3">{user.email}</td><td className="p-3"><select className="rounded bg-slate-800 p-1" value={user.roles[0]?.name} onChange={(event) => void updateRole(user.id, event.target.value as (typeof roles)[number])}>{roles.map((role) => <option key={role}>{role}</option>)}</select></td><td className="p-3">{user.is_active ? "Active" : "Inactive"}</td><td className="space-x-3 p-3"><button className="text-cyan-400" onClick={() => void updateActive(user)} type="button">{user.is_active ? "Deactivate" : "Activate"}</button><button className="text-cyan-400" onClick={() => setSelectedUser(user.id)} type="button">Reset password</button></td></tr>)}</tbody></table></div></section>;
}
