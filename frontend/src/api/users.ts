import { apiRequest, type User } from "./client";

type UserListResponse = { items: User[]; offset: number; limit: number };

export function listUsers(token: string): Promise<UserListResponse> {
  return apiRequest<UserListResponse>("/users", { token });
}

export function createUser(
  token: string,
  input: { email: string; password: string; role_name: "SUPER-ADMIN" | "ADMIN" },
): Promise<User> {
  return apiRequest<User>("/users", { method: "POST", token, body: JSON.stringify(input) });
}

export function setUserActive(token: string, userId: string, isActive: boolean): Promise<User> {
  return apiRequest<User>(`/users/${userId}/active`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ is_active: isActive }),
  });
}

export function assignUserRole(
  token: string,
  userId: string,
  roleName: "SUPER-ADMIN" | "ADMIN",
): Promise<User> {
  return apiRequest<User>(`/users/${userId}/role`, {
    method: "PUT",
    token,
    body: JSON.stringify({ role_name: roleName }),
  });
}

export function resetUserPassword(token: string, userId: string, newPassword: string): Promise<void> {
  return apiRequest<void>(`/users/${userId}/password`, {
    method: "PUT",
    token,
    body: JSON.stringify({ new_password: newPassword }),
  });
}
