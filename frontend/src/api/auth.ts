import { apiJson } from "./client";
import type { TokenResponse, UserRegisterRequest, UserResponse } from "./types";

export function register(body: UserRegisterRequest): Promise<UserResponse> {
  return apiJson<UserResponse>("/api/auth/register", { method: "POST", json: body, auth: false });
}

export function login(body: UserRegisterRequest): Promise<TokenResponse> {
  return apiJson<TokenResponse>("/api/auth/login", { method: "POST", json: body, auth: false });
}

export function logout(refreshToken: string): Promise<{ message: string }> {
  return apiJson("/api/auth/logout", { method: "POST", json: { refresh_token: refreshToken }, auth: false });
}
