"use client";

const TOKEN_KEY = "ohship_token";
const API_KEY_STORAGE = "ohship_api_key";
const ORG_KEY = "ohship_org_id";
const PROJECT_KEY = "ohship_project";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(API_KEY_STORAGE);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(API_KEY_STORAGE);
}

export function setApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE, key);
}

export function getOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ORG_KEY);
}

export function setOrgId(id: string): void {
  localStorage.setItem(ORG_KEY, id);
}

export function clearOrgId(): void {
  localStorage.removeItem(ORG_KEY);
}

export function getProject(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(PROJECT_KEY);
}

export function setProject(name: string): void {
  localStorage.setItem(PROJECT_KEY, name);
}

export function clearProject(): void {
  localStorage.removeItem(PROJECT_KEY);
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(API_KEY_STORAGE);
  localStorage.removeItem(ORG_KEY);
  localStorage.removeItem(PROJECT_KEY);
}

export function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}
