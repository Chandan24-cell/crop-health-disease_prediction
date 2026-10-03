import { safeStorage } from "./storage.js";

const REMINDERS_KEY = "fieldnote-spray-reminders";

export function getSavedReminders() {
  try {
    const value = JSON.parse(safeStorage.get(REMINDERS_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

export function saveReminder(reminder) {
  safeStorage.set(REMINDERS_KEY, JSON.stringify([...getSavedReminders(), reminder]));
}

export function removeReminder(id) {
  safeStorage.set(REMINDERS_KEY, JSON.stringify(getSavedReminders().filter((r) => r.id !== id)));
}

export async function requestNotificationPermission() {
  if (!("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission !== "denied") return (await Notification.requestPermission()) === "granted";
  return false;
}

export async function scheduleSprayReminder({ disease, action, daysFromNow }) {
  const granted = await requestNotificationPermission();
  const reminderDate = new Date();
  reminderDate.setDate(reminderDate.getDate() + daysFromNow);
  const reminder = {
    id: `rem-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    disease,
    action,
    scheduledFor: reminderDate.toLocaleDateString(),
    daysFromNow,
    created: new Date().toISOString(),
    permissionGranted: granted,
  };
  saveReminder(reminder);
  if (granted && "Notification" in window) {
    try {
      new Notification("Spray Reminder Set — Fieldnote", {
        body: `Reminder for ${disease}: ${action} scheduled for ${reminderDate.toLocaleDateString()}.`,
        icon: "./favicon.svg",
      });
    } catch {
      // Notifications may be unavailable while the page is foregrounded.
    }
  }
  return reminder;
}
