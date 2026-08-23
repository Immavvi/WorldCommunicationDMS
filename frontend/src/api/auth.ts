import { apiRequest, type User } from "./client";

export type LoginResponse = { access_token: string; token_type: "bearer"; user: User };

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getCurrentUser(token: string): Promise<User> {
  return apiRequest<User>("/auth/me", { token });
}

export function changePassword(
  token: string,
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  return apiRequest<void>("/auth/change-password", {
    method: "POST",
    token,
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}
