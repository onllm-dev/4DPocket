export interface StoredAuth {
  serverUrl: string;
  token: string | null;
  username: string | null;
}

export interface ItemRead {
  id: string;
  url: string | null;
  title: string | null;
  description: string | null;
  source_platform: string;
  item_type: string;
  summary: string | null;
  is_favorite: boolean;
  created_at: string;
}

export interface HighlightRead {
  id: string;
  item_id: string;
  text: string;
  note: string | null;
  color: string;
  position: Record<string, unknown> | null;
  created_at: string;
}

export interface CheckUrlResponse {
  exists: boolean;
  item_id?: string;
  title?: string;
}

export interface UserRead {
  id: string;
  email: string;
  username: string;
  display_name: string | null;
  role: string;
}
