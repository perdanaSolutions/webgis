export const getErrorMessage = (
  error: any,
  fallbackMessage: string = "Terjadi kesalahan. Silakan coba lagi.",
): string => {
  const data = error?.data;

  // 1. Format error array dari backend
  if (data?.errors && Array.isArray(data.errors)) {
    const errorMessages: string[] = [];

    data.errors.forEach((err: { field: string; msg: string }) => {
      if (!err?.msg) return;
      if (err.field && err.field !== "global" && err.field !== "auth") {
        errorMessages.push(`${err.field}: ${err.msg}`);
      } else {
        errorMessages.push(err.msg);
      }
    });

    if (errorMessages.length > 0) {
      return errorMessages.join(", ");
    }
  }

  if (typeof data?.errors === "string") return data.errors;
  if (typeof data?.detail === "string") return data.detail;

  // 2. Fallback: detail biasa, network/mixed-content (tanpa body), atau pesan generik
  return data?.detail || error?.message || fallbackMessage;
};
