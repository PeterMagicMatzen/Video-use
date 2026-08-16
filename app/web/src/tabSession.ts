export const TAB_FOLDER_KEY = "video-use:tab-folder";

export type BootAction = { mode: "empty" } | { mode: "restore"; folder: string };

export function bootFromTab(stored: string | null | undefined): BootAction {
  const folder = (stored ?? "").trim();
  if (!folder) return { mode: "empty" };
  return { mode: "restore", folder };
}

export function shouldAdoptServerState(tabFolder: string | null | undefined, serverFolder: string | null | undefined): boolean {
  return Boolean(tabFolder && serverFolder && tabFolder === serverFolder);
}

export function readTabFolder(storage: Pick<Storage, "getItem"> = sessionStorage): string | null {
  try {
    const value = storage.getItem(TAB_FOLDER_KEY);
    return value && value.trim() ? value : null;
  } catch {
    return null;
  }
}

export function writeTabFolder(folder: string, storage: Pick<Storage, "setItem"> = sessionStorage): void {
  try {
    storage.setItem(TAB_FOLDER_KEY, folder);
  } catch {
    /* private mode */
  }
}

export function clearTabFolder(storage: Pick<Storage, "removeItem"> = sessionStorage): void {
  try {
    storage.removeItem(TAB_FOLDER_KEY);
  } catch {
    /* private mode */
  }
}
