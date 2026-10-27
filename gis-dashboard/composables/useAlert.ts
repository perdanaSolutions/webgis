import { shallowRef } from "vue";
import { createAlertController, type AlertItem } from "~/utils/alertQueue";

// Singleton modul: popup hanya dipanggil dari sisi client (event handler),
// komponen <AppAlert> dirender di dalam <ClientOnly>.
const currentAlert = shallowRef<AlertItem | null>(null);
const controller = createAlertController({
  onChange: (item) => {
    currentAlert.value = item;
  },
});

/**
 * Popup global ala SweetAlert.
 *   const alert = useAlert()
 *   await alert.error('Login gagal', 'Email atau password salah')
 *   if (await alert.confirm('Hapus data?', 'Data tidak bisa dikembalikan', { confirmText: 'Hapus' })) { ... }
 */
export function useAlert() {
  return controller;
}

export function useAlertState() {
  return currentAlert;
}
