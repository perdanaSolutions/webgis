/**
 * Antrean popup global ala SweetAlert (logika murni, tanpa Vue/DOM agar mudah dites).
 * Satu popup tampil pada satu waktu; panggilan berikutnya menunggu di antrean.
 */
export type AlertIcon = "success" | "error" | "warning" | "info" | "question";

export interface AlertOptions {
  title?: string;
  /** Teks biasa (selalu dirender sebagai teks, tidak pernah sebagai HTML). */
  text?: string;
  icon?: AlertIcon;
  confirmText?: string;
  cancelText?: string;
  showCancel?: boolean;
  /** Tutup otomatis setelah n milidetik (hasil = false). */
  timer?: number;
  /** Tutup saat klik backdrop / tombol ESC (default true). */
  dismissible?: boolean;
}

export interface AlertItem extends Required<Omit<AlertOptions, "timer">> {
  id: number;
  timer: number;
}

type Entry = { item: AlertItem; resolve: (v: boolean) => void };

export const ALERT_DEFAULTS = {
  confirmText: "OK",
  cancelText: "Batal",
} as const;

export function createAlertController(opts: {
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (h: unknown) => void;
  onChange?: (current: AlertItem | null) => void;
} = {}) {
  const setTimer = opts.setTimer ?? ((fn, ms) => setTimeout(fn, ms));
  const clearTimer = opts.clearTimer ?? ((h) => clearTimeout(h as ReturnType<typeof setTimeout>));
  const queue: Entry[] = [];
  let active: Entry | null = null;
  let timerHandle: unknown = null;
  let seq = 0;

  function emit() {
    opts.onChange?.(active ? active.item : null);
  }

  function next() {
    active = queue.shift() ?? null;
    emit();
    if (active && active.item.timer > 0) {
      const id = active.item.id;
      timerHandle = setTimer(() => {
        if (active?.item.id === id) close(false);
      }, active.item.timer);
    }
  }

  function close(result: boolean) {
    if (!active) return;
    if (timerHandle !== null) {
      clearTimer(timerHandle);
      timerHandle = null;
    }
    const done = active;
    active = null;
    done.resolve(result);
    next();
  }

  function open(o: AlertOptions): Promise<boolean> {
    const item: AlertItem = {
      id: ++seq,
      title: o.title ?? "",
      text: o.text ?? "",
      icon: o.icon ?? "info",
      confirmText: o.confirmText ?? ALERT_DEFAULTS.confirmText,
      cancelText: o.cancelText ?? ALERT_DEFAULTS.cancelText,
      showCancel: o.showCancel ?? false,
      timer: o.timer && o.timer > 0 ? o.timer : 0,
      dismissible: o.dismissible ?? true,
    };
    return new Promise<boolean>((resolve) => {
      queue.push({ item, resolve });
      if (!active) next();
    });
  }

  type Extra = Omit<AlertOptions, "title" | "text" | "icon">;
  const shortcut = (icon: AlertIcon) => (title: string, text?: string, extra: Extra = {}) =>
    open({ ...extra, title, text, icon });

  return {
    open,
    close,
    confirm: (title: string, text?: string, extra: Extra = {}) =>
      open({ icon: "question", ...extra, title, text, showCancel: true }),
    success: shortcut("success"),
    error: shortcut("error"),
    warning: shortcut("warning"),
    info: shortcut("info"),
    current: () => (active ? active.item : null),
    pending: () => queue.length,
    /** Tutup semua (popup aktif + antrean) dengan hasil false. */
    clearAll() {
      const rest = queue.splice(0);
      close(false);
      rest.forEach((e) => e.resolve(false));
      // close() mungkin telah mengambil item dari antrean yang sudah dikosongkan
      if (active) close(false);
    },
  };
}

export type AlertController = ReturnType<typeof createAlertController>;
